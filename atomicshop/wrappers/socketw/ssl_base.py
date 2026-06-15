import ssl
import struct
from typing import Tuple, Optional

from tlslite.messages import ClientHello as _TlsLiteClientHello
from tlslite.utils.codec import Parser as _TlsLiteParser

from . import receiver


def get_certificate_from_socket(socket):
    """Get certificate from socket.
    The certificate will be bytes in DER x509 format (commonly found in files with the .cer extension).

    :param socket: socket to get certificate from
    :return: certificate
    """
    return socket.getpeercert(True)


def convert_der_x509_bytes_to_pem_string(certificate) -> str:
    """Convert certificate from socket to PEM format.

    :param certificate: certificate to convert
    :return: certificate in PEM format
    """

    return ssl.DER_cert_to_PEM_cert(certificate)


def consume_client_hello(
        client_socket,
        timeout: float = 10.0,
        max_bytes: int = 16384,
) -> Tuple[
        bool,
        Optional[list[str]],
        bytes,
        Optional[Tuple[str, Optional[str]]]
]:
    """
    Consume the first bytes of a just-accepted socket, classify them as TLS
    vs non-TLS, and — if TLS — parse the client's ALPN offers out of the
    ClientHello record.

    Why this exists
    ---------------
    Replaces the old peek-based pair (``is_tls`` + ``peek_alpn_offers``, now
    retired at the bottom of this module). The peek approach relied on
    ``MSG_PEEK`` to inspect a ClientHello without consuming bytes, which has
    two fundamental limits:

    * ``MSG_PEEK`` returns only what's currently sitting in the kernel receive
      buffer. A ClientHello that spans multiple TCP segments (common under
      TLS 1.3 with post-quantum key_share, ~1500–2500 B) comes back as a
      short read and the ALPN parser has to bail. The upstream leg then
      never receives a faithful ALPN offer list.
    * Each stage (detect-TLS, read-header, read-record) cost a separate
      ``recv(MSG_PEEK)`` syscall on kernel buffer state that isn't stable
      between calls.

    The sans-io fix — applied here — is to *consume* bytes into a Python
    buffer, parse the record in Python, then re-inject the same bytes into
    OpenSSL via a ``MemoryBIO`` so the real TLS handshake replays them (see
    ``creator.wrap_bio_server_with_error_message``). For the non-TLS branch
    the caller wraps the raw socket in ``BufferedSocket(raw, buffered)`` so
    downstream code still sees the consumed bytes as if they were on the wire.

    :param client_socket: the just-accepted TCP socket.
    :param timeout: per-``recv`` timeout (seconds) passed through to
        ``receiver.recv_exact``. ``None`` means block indefinitely.
    :param max_bytes: hard ceiling on how many bytes we'll consume trying to
        assemble a full record. TLS record spec tops out at 16384, so that's
        our default. If a peer claims a bigger record we still return
        ``is_tls=True`` (OpenSSL can reject it later) but skip ALPN parsing
        rather than risk a runaway read.

    :raises TimeoutError: if a ``recv()`` exceeds ``timeout`` while we're
        trying to read sniff bytes or the record body.
    :raises ConnectionError: if the peer closes before the requested byte
        count is available — partial records can't be parsed or re-injected.

    :return: a 4-tuple ``(is_tls, alpn_offers, buffered, tls_properties)``:
      * ``is_tls`` — ``True`` if the first 3 bytes look like the start of a
        TLS handshake record (content type 0x16 + version 0x03xx).
      * ``alpn_offers`` — client's ALPN offer list in the order the client
        sent them, or ``None`` when: the ALPN extension is absent, the
        declared record length exceeds ``max_bytes``, or parsing blows up.
        ``None`` means the TLS path should proceed *without* faithful
        upstream ALPN mirroring (same degradation as the retired peek
        path's short-read fallthrough).
      * ``buffered`` — every byte we consumed from the socket. The caller
        owns these: TLS path feeds them into ``MemoryBIO.incoming.write``,
        non-TLS path wraps them with ``BufferedSocket``. We can never
        "un-read" bytes back into a socket, so the caller *must* hand them
        somewhere downstream.
      * ``tls_properties`` — ``(content_type_string, version_string)`` for
        logging, matching the shape of the retired ``is_tls()`` return.
        ``None`` when ``is_tls`` is ``False``.
    """

    # ---- Step 1: sniff the first 3 bytes to decide "TLS or not?" ----
    # The TLS record header is 5 bytes (content_type + version_major +
    # version_minor + length_hi + length_lo). Bytes 0-2 are enough to
    # decide whether this is the start of a TLS handshake at all, so we
    # consume 3 bytes up front — the smallest commitment that still gives
    # us a confident TLS sniff. Both branches (TLS / non-TLS) will re-use
    # these same bytes downstream, so there's no waste.
    buffered = receiver.recv_exact(client_socket, 3, timeout=timeout)
    content_type, version_major, version_minor = buffered[0], buffered[1], buffered[2]

    # Content type 0x16 == Handshake. The first record of a TLS connection
    # *must* be a ClientHello Handshake record — any other content type
    # (Alert 0x15, AppData 0x17, ChangeCipherSpec 0x14) is either a protocol
    # violation or not TLS at all. We also require the version byte to start
    # with 0x03 (SSLv3 / TLSv1.x) so that arbitrary binary payloads that
    # happen to start with 0x16 don't masquerade as TLS.
    if content_type != 0x16 or version_major != 0x03:
        return False, None, buffered, None

    # ---- Step 2: build a human-readable tls_properties tuple for logs ----
    # Mirrors the shape the retired ``is_tls()`` returned so log lines
    # downstream (tls_type / tls_version) don't change format.
    content_type_map = {
        0x14: "Change Cipher Spec",
        0x15: "Alert",
        0x16: "Handshake",
        0x17: "Application Data",
        0x18: "Heartbeat",
    }
    version_map = {
        (0x03, 0x00): "SSLv3.0",
        (0x03, 0x01): "TLSv1.0",
        (0x03, 0x02): "TLSv1.1",
        (0x03, 0x03): "TLSv1.2/1.3",
        # 1.2 vs 1.3 cannot be distinguished from the legacy record-layer
        # version byte alone — the real version only becomes visible via
        # ``SSLObject.version()`` after the handshake completes.
    }
    tls_properties = (
        content_type_map.get(content_type, "Handshake"),
        version_map.get((version_major, version_minor)),
    )

    # ---- Step 3: top up to the full 5-byte record header ----
    # Bytes 3-4 carry the record body length as a big-endian uint16. We
    # need them before we know how many more bytes to read. Append onto
    # the same ``buffered`` bytes object so the caller gets the full record
    # as a single contiguous blob.
    buffered += receiver.recv_exact(client_socket, 2, timeout=timeout)
    record_length = (buffered[3] << 8) | buffered[4]
    total_needed = 5 + record_length

    # ---- Step 4: refuse runaway records ----
    # Real ClientHellos rarely exceed ~3 KB even with TLS 1.3 + post-quantum
    # key_share; the TLS spec caps a single record at 16384 bytes. If a peer
    # claims a bigger record we fall through to the TLS path (letting
    # OpenSSL reject it properly during the real handshake) but skip ALPN
    # parsing — better to lose ALPN mirroring than to block on a malicious
    # or malformed length field.
    if total_needed > max_bytes:
        return True, None, buffered, tls_properties

    # ---- Step 5: top up to the full record body ----
    # We already have 5 bytes (header), still need ``record_length`` more.
    buffered += receiver.recv_exact(client_socket, record_length, timeout=timeout)

    # ---- Step 6: parse ALPN from the ClientHello ----
    # Returns None on any failure (malformed record, missing ALPN extension,
    # unparseable ClientHello) — the TLS path still proceeds from the buffered
    # bytes, just without faithful upstream ALPN mirroring.
    alpn_offers = _parse_alpn_from_client_hello_record(buffered)

    return True, alpn_offers, buffered, tls_properties


def _parse_alpn_from_client_hello_record(record: bytes) -> Optional[list[str]]:
    """Extract the client's ALPN offers (in client order) from a full ClientHello
    record, or None when the record isn't a ClientHello, carries no ALPN extension,
    or won't parse. Never raises — the caller reads None as "no ALPN mirroring".

    ClientHello dissection is delegated to tlslite-ng; we only strip the record +
    handshake framing (already validated by the accept path) and read the ALPN
    protocol list back out.
    """
    body = record[5:]                          # drop the 5-byte TLS record header
    if len(body) < 4 or body[0] != 0x01:       # handshake header; 0x01 == ClientHello
        return None
    try:
        parser = _TlsLiteParser(body)
        parser.get(1)                          # consume handshake type; parse() reads its own 3-byte length
        client_hello = _TlsLiteClientHello().parse(parser)
        for extension in (client_hello.extensions or []):
            names = getattr(extension, "protocol_names", None)  # only ALPNExtension has this
            if names is not None:
                return [bytes(name).decode("ascii") for name in names] or None
    except Exception:                          # malformed ClientHello -> degrade to no ALPN mirroring
        return None
    return None

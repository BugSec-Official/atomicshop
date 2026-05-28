import ssl
import struct
from typing import Tuple, Optional

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
    # Any parsing failure (malformed record, missing ALPN extension, unknown
    # extension structure) degrades to "no ALPN mirroring" rather than
    # aborting the TLS path — the real handshake can still proceed from the
    # bytes we've buffered.
    try:
        alpn_offers = _parse_alpn_from_client_hello_record(buffered)
    except (struct.error, IndexError, ValueError):
        alpn_offers = None

    return True, alpn_offers, buffered, tls_properties


def _parse_alpn_from_client_hello_record(record: bytes) -> Optional[list[str]]:
    """
    Parse a full TLS record containing a ClientHello and extract the ALPN
    extension's protocol list. Returns None if the record is not a ClientHello
    or the ALPN extension is absent. Raises on malformed input.
    """
    # TLS record header: [content_type(1) version(2) length(2)]
    # We already know content_type == 0x16 at this point.
    body = record[5:]

    # Handshake header: [handshake_type(1) length(3)]
    if len(body) < 4:
        return None
    handshake_type = body[0]
    if handshake_type != 0x01:  # ClientHello
        return None

    # Skip handshake header.
    ch = body[4:]
    # legacy_version(2) + random(32)
    offset = 2 + 32
    # session_id: 1-byte length prefix.
    sid_len = ch[offset]
    offset += 1 + sid_len
    # cipher_suites: 2-byte length prefix.
    cs_len = (ch[offset] << 8) | ch[offset + 1]
    offset += 2 + cs_len
    # compression_methods: 1-byte length prefix.
    cm_len = ch[offset]
    offset += 1 + cm_len
    # extensions: 2-byte length prefix, then a sequence of [type(2) length(2) data].
    if offset + 2 > len(ch):
        return None
    ext_total = (ch[offset] << 8) | ch[offset + 1]
    offset += 2
    ext_end = offset + ext_total
    if ext_end > len(ch):
        return None

    while offset + 4 <= ext_end:
        ext_type = (ch[offset] << 8) | ch[offset + 1]
        ext_len = (ch[offset + 2] << 8) | ch[offset + 3]
        ext_data_start = offset + 4
        ext_data_end = ext_data_start + ext_len
        if ext_data_end > ext_end:
            return None

        # 0x0010 = application_layer_protocol_negotiation
        if ext_type == 0x0010:
            return _parse_alpn_extension_body(ch[ext_data_start:ext_data_end])

        offset = ext_data_end

    return None


def _parse_alpn_extension_body(data: bytes) -> Optional[list[str]]:
    """
    Parse the inner list of the ALPN extension: [list_length(2)] then a
    sequence of length-prefixed (1 byte) protocol names.
    """
    if len(data) < 2:
        return None
    list_length = (data[0] << 8) | data[1]
    if 2 + list_length != len(data):
        return None

    offset = 2
    offers: list[str] = []
    while offset < len(data):
        name_length = data[offset]
        offset += 1
        if offset + name_length > len(data):
            return None
        name_bytes = data[offset:offset + name_length]
        try:
            offers.append(name_bytes.decode("ascii"))
        except UnicodeDecodeError:
            return None
        offset += name_length

    return offers or None


# ======================================================================================
# Retired implementations — kept for historical reference only.
# Do NOT call these from new code. See ``consume_client_hello`` above for the live
# function used by the sans-io consume+MemoryBIO accept path.
# ======================================================================================


def __is_tls(client_socket, timeout: float = None) -> Tuple[bool, Optional[Tuple[str, Optional[str]]]]:
    # THIS IS NO LONGER USED, FOR REFERENCE ONLY.
    """
    Peek-based TLS sniff — superseded by ``consume_client_hello``.

    Why this was retired
    --------------------
    Used ``MSG_PEEK`` on the raw socket to look at the first 3 bytes without
    consuming them, then decided TLS-or-not from the content_type and version
    byte. Two problems drove replacement:

    * The peek returns only what's already in the kernel receive buffer. A
      slow peer can arrive byte-by-byte and the peek comes back short.
    * The downstream ``peek_alpn_offers`` peek was a *separate* syscall on
      kernel buffer state that isn't stable between calls — by the time we
      asked for more bytes, the buffer contents could have shifted.

    The replacement (``consume_client_hello``) reads bytes into a Python
    buffer once, inspects them in Python, and re-injects them into OpenSSL
    via a ``MemoryBIO`` so the real handshake still sees a faithful record.

    :param client_socket: Socket object.
    :param timeout: float, Timeout in seconds for the peek.

    :return: tuple (is_tls: bool, tls_properties: (content_type_str, version_str) | None).
    """
    peek_bytes = receiver.__peek_first_bytes(client_socket, 3, timeout=timeout)

    content_type = peek_bytes[0]
    version_major = peek_bytes[1]
    version_minor = peek_bytes[2]

    if content_type != 0x16 or version_major != 0x03:
        return False, None

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
    }
    tls_properties = (
        content_type_map.get(content_type, "Handshake"),
        version_map.get((version_major, version_minor)),
    )
    return True, tls_properties


def __peek_alpn_offers(client_socket, timeout: float = None) -> Optional[list[str]]:
    # THIS IS NO LONGER USED, FOR REFERENCE ONLY.
    """
    Peek-based ClientHello ALPN extractor — superseded by ``consume_client_hello``.

    Why this was retired
    --------------------
    Peeked the 5-byte record header, read the declared record length out of
    bytes 3-4, then peeked that many bytes again and handed them to
    ``_parse_alpn_from_client_hello_record``. Failed whenever the ClientHello
    spanned multiple TCP segments (common under TLS 1.3 + post-quantum
    key_share, ~1500-2500 B) because ``MSG_PEEK`` only returns what's
    currently sitting in the kernel receive buffer. Short peek → short
    parse → ALPN offers lost → upstream leg can't mirror client ALPN
    faithfully.

    Consumed approach (``consume_client_hello``) loops ``recv()`` until the
    full record has arrived, so fragmentation doesn't drop ALPN info on
    the floor.

    :param client_socket: Socket object.
    :param timeout: float, per-peek timeout in seconds.

    :return: list of ALPN offer strings in client order, or ``None`` if the
        ALPN extension is absent, the peek came up short, or parsing failed.
    """
    try:
        header = receiver.__peek_first_bytes(client_socket, 5, timeout=timeout)
    except TimeoutError:
        return None

    if len(header) < 5:
        return None

    record_length = (header[3] << 8) | header[4]
    total_needed = 5 + record_length

    # Cap to avoid a runaway peek — the record spec tops out at 16384.
    if total_needed > 4096:
        return None

    try:
        record = receiver.__peek_first_bytes(client_socket, total_needed, timeout=timeout)
    except TimeoutError:
        return None

    if len(record) < total_needed:
        return None

    try:
        return _parse_alpn_from_client_hello_record(record)
    except (struct.error, IndexError, ValueError):
        return None

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


def is_tls(
        client_socket,
        timeout: float = None
) -> Optional[Tuple[str, str]]:
    """
    Return protocol type of the incoming socket after 'accept()'.
    :param client_socket: incoming socket after 'accept()'.
    :param timeout: optional timeout for receiving/peeking the first bytes.
    :return: tuple with content type, protocol type + version.
        If the length of the first bytes is less than 3, return None.
    """

    first_bytes = receiver.peek_first_bytes(client_socket, bytes_amount=3, timeout=timeout)

    # Sometimes only one byte is available, so we need to handle that case.
    # convert to a tuple of ints, add three Nones, and keep only the first 3 items.
    content_type, version_major, version_minor = (tuple(first_bytes) + (None, None, None))[:3]

    # Map TLS content types to their string representation.
    content_type_map = {
        0x14: "Change Cipher Spec",
        0x15: "Alert",
        0x16: "Handshake",
        0x17: "Application Data",
        0x18: "Heartbeat"
    }

    # Map TLS version bytes to their string representation.
    version_map = {
        (0x03, 0x00): "SSLv3.0",
        (0x03, 0x01): "TLSv1.0",
        (0x03, 0x02): "TLSv1.1",
        (0x03, 0x03): "TLSv1.2/1.3"
        # Remember, you can't definitively differentiate 1.2 and 1.3 just from these bytes
    }

    # Get the tuple of the type and version as strings.
    tls_content_and_version_tuple: tuple[str, str] = \
        content_type_map.get(content_type), version_map.get((version_major, version_minor))

    # If both parts of the tuple are not None, return the protocol type.
    if tls_content_and_version_tuple[0]:
        return tls_content_and_version_tuple
    else:
        return None


def peek_alpn_offers(
        client_socket,
        timeout: float = None,
        max_peek_bytes: int = 4096
) -> Optional[list[str]]:
    """
    Peek the client's ClientHello (without consuming bytes) and return the ALPN
    offers the client proposed, as a list of protocol-name strings, in the
    order the client sent them.

    Returns None if:
      - the record is not a TLS handshake ClientHello,
      - the ALPN extension is absent,
      - the ClientHello spans multiple TCP segments and only a partial record
        is peek-able in one read,
      - any parsing error occurs.

    Peek-only: bytes remain in the socket buffer for the real TLS handshake.
    """
    # First, peek 5-byte TLS record header to learn the record length.
    try:
        header = receiver.peek_first_bytes(client_socket, bytes_amount=5, timeout=timeout)
    except TimeoutError:
        return None
    if len(header) < 5:
        return None

    content_type = header[0]
    # Handshake record.
    if content_type != 0x16:
        return None

    record_length = (header[3] << 8) | header[4]
    total_needed = 5 + record_length
    if total_needed > max_peek_bytes:
        return None

    try:
        record = receiver.peek_first_bytes(client_socket, bytes_amount=total_needed, timeout=timeout)
    except TimeoutError:
        return None
    if len(record) < total_needed:
        return None

    try:
        return _parse_alpn_from_client_hello_record(record)
    except (struct.error, IndexError, ValueError):
        return None


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

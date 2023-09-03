import ssl
from typing import Union, Tuple, Optional

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


def get_protocol_type(client_socket) -> Union[Tuple[Optional[str], Optional[Tuple[str, str]]], Tuple[None, None]]:
    """
    Return protocol type of the incoming socket after 'accept()'.
    :param client_socket: incoming socket after 'accept()'.
    :return: string with protocol type, (tuple with content type, protocol type + version).
    """

    first_bytes = receiver.peek_first_bytes(client_socket, bytes_amount=3)

    # Ensure we got enough data.
    if len(first_bytes) < 3:
        return None, None

    # Extract the content type and version
    content_type, version_major, version_minor = first_bytes

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
        (0x03, 0x00): "SSL 3.0",
        (0x03, 0x01): "TLS 1.0",
        (0x03, 0x02): "TLS 1.1",
        (0x03, 0x03): "TLS 1.2/1.3"
        # Remember, you can't definitively differentiate 1.2 and 1.3 just from these bytes
    }

    # Get the tuple of the type and version as strings.
    tls_content_and_version_tuple: tuple =\
        content_type_map.get(content_type), version_map.get((version_major, version_minor))

    # If both parts of the tuple are not None, return the protocol type.
    if tls_content_and_version_tuple[0] and tls_content_and_version_tuple[1]:
        return 'tls', tls_content_and_version_tuple
    else:
        return None, None

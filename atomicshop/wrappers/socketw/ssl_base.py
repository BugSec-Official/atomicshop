import ssl


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

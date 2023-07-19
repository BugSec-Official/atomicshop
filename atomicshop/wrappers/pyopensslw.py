import random
from OpenSSL import crypto

from .. import certificates


def convert_der_to_x509_object(certificate) -> crypto.X509:
    """Convert certificate from socket (or der format in bytes) to pyOpenSSL x509 object.

    :param certificate: certificate to convert
    :return: certificate in x509 object
    """

    return crypto.load_certificate(crypto.FILETYPE_ASN1, certificate)


def convert_pem_to_x509_object(certificate) -> crypto.X509:
    """Convert certificate in PEM format to pyOpenSSL x509 object.

    :param certificate: certificate to convert
    :return: certificate in x509 object
    """

    return crypto.load_certificate(crypto.FILETYPE_PEM, certificate)


def convert_x509_object_to_pem(certificate):
    """Convert certificate to PEM format.

    :param certificate: certificate to convert.
    :return: certificate in PEM format.
    """

    return crypto.dump_certificate(crypto.FILETYPE_PEM, certificate)


def convert_cryptography_object_to_pyopenssl(certificate):
    """Convert certificate from 'cryptography' module to pyOpenSSL x509 object.

    :param certificate: certificate in x509 object of 'cryptography' module.
    :return: certificate in x509 object of pyOpenSSL module.
    """

    return crypto.X509.from_cryptography(certificate)


def convert_pyopenssl_object_to_cryptography(certificate):
    """Convert certificate from pyOpenSSL x509 object to 'cryptography' module x509 object.

    :param certificate: certificate in x509 object of pyOpenSSL module.
    :return: certificate in x509 object of 'cryptography' module.
    """

    return crypto.X509.to_cryptography(certificate)


def generate_private_key(crypto_type=crypto.TYPE_RSA, bits: int = 2048):
    """Generate private key.

    Using pyOpenSSL.

    :param crypto_type: key type: crypto.TYPE_RSA or crypto.TYPE_DSA. Default: crypto.TYPE_RSA.
    :param bits: integer, number of bits. Default: 2048 bits.
    :return: private key.
    """
    # Create a new private key for the certificate
    key = crypto.PKey()
    key.generate_key(crypto_type, bits)
    return key


def generate_certificate_signing_request(domain=None, certificate=None, key=None, hash_algo: str = 'sha256'):
    """Generate CSR - Certificate Signing Request.

    Using pyOpenSSL.

    :param domain: domain name that will be used for CSR CN field.
        If 'certificate' and 'domain' are provided, 'domain' will be ignored.
    :param certificate: certificate object. If provided, domain name will be taken from it.
        If 'certificate' and 'domain' are provided, 'domain' will be ignored.
    :param key: private key. If not provided, a new RSA 2048-bit key will be generated.
    :param hash_algo: string, hash algorithm. Default: 'sha256'.
    :return: certificate request.
    """

    if not domain and not certificate:
        raise ValueError('Either domain or certificate should be provided.')

    # If no key provided, generate a new one.
    if not key:
        key = generate_private_key()

    # Create a new certificate request.
    csr_request = crypto.X509Req()

    if not certificate:
        # Set the domain name.
        csr_request.get_subject().CN = domain
    else:
        # Set the domain name from provided certificate.
        csr_request.get_subject().CN = certificate.get_subject().CN

    # Set the public key.
    csr_request.set_pubkey(key)
    # Sign the request with the private key.
    csr_request.sign(key, hash_algo)

    return key, csr_request


def generate_server_certificate_empty(
        certname,
        seconds_not_before: int = 0,
        seconds_not_after: int = certificates.SECONDS_NOT_AFTER_3_YEARS):
    """Generate empty server certificate.

    :param certname: string, certificate name.
    :param seconds_not_before: int, number of seconds before the certificate is valid. Probably should be 0.
    :param seconds_not_after: int, number of seconds after the certificate is valid. Maximum is 39 months.
    :return: certificate.
    """

    cert = crypto.X509()
    cert.set_serial_number(random.randint(0, 2 ** 64 - 1))
    cert.get_subject().CN = certname

    cert.set_version(2)
    cert.gmtime_adj_notBefore(seconds_not_before)
    cert.gmtime_adj_notAfter(seconds_not_after)
    return cert


def generate_server_certificate_ca_signed(
        ca_cert, ca_key,
        host: str = None,
        certificate=None,
        wildcard: bool = False,
        hash_algo: str = 'sha256',
        is_host_ip: bool = False,
        cert_ips=None,
        cert_fqdns=None,
        seconds_not_before: int = 0,
        seconds_not_after: int = certificates.SECONDS_NOT_AFTER_3_YEARS
):

    if not host and not certificate:
        raise ValueError('Must provide host or certificate')

    if not cert_ips:
        cert_ips = set()
    if not cert_fqdns:
        cert_fqdns = set()

    # The host name must be encoded in UTF-8. Most of the examples state that it can be used as string, which is great,
    # but in reality there will be numerous SSL Protocol mismatch errors from the client side.
    host_utf8 = host.encode('utf-8')

    # Generate key and CSR - Certificate Signing Request.
    key, csr_request = generate_certificate_signing_request(domain=host_utf8, certificate=certificate)

    if not certificate:
        # Generate Cert
        server_certificate = generate_server_certificate_empty(host_utf8, seconds_not_before, seconds_not_after)
    else:
        server_certificate = certificate

    server_certificate.set_issuer(ca_cert.get_subject())
    server_certificate.set_pubkey(csr_request.get_pubkey())

    if not certificate:
        all_hosts = ['DNS:'+host]

        if wildcard:
            all_hosts += ['DNS:*.' + host]

        elif is_host_ip:
            all_hosts += ['IP:' + host]

        all_hosts += ['IP: {}'.format(ip) for ip in cert_ips]
        all_hosts += ['DNS: {}'.format(fqdn) for fqdn in cert_fqdns]

        san_hosts = ', '.join(all_hosts)
        san_hosts = san_hosts.encode('utf-8')

        server_certificate.add_extensions([
            crypto.X509Extension(b'subjectAltName',
                                 False,
                                 san_hosts)])

    server_certificate.sign(ca_key, hash_algo)
    return server_certificate, key


def convert_certificate_file_to_string(certificate_path: str):
    """Convert certificate to string.

    :param certificate_path: path to certificate.
    :return: certificate as string.
    """

    cert = crypto.load_certificate(crypto.FILETYPE_PEM, open(certificate_path).read())
    return crypto.dump_certificate(crypto.FILETYPE_TEXT, cert)

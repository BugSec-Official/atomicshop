import ipaddress
from datetime import datetime, timedelta, timezone
from secrets import randbits

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.x509.oid import NameOID
from OpenSSL import crypto

from .. import certificates

# pyOpenSSL 26.4.0 removed X509Req, X509Extension and X509.add_extensions. Certificates that need extensions
# and certificate requests are built with cryptography's builders; certificates are handed back as pyOpenSSL
# X509 objects, which the callers keep working with.


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


def _hash_algorithm(hash_algo: str) -> hashes.HashAlgorithm:
    """'sha256' -> hashes.SHA256(), the form cryptography's builders take."""
    return getattr(hashes, hash_algo.upper())()


def name_from_common_name(name) -> x509.Name:
    # X.520 ub-common-name caps CN at 64 characters; long FQDNs overflow the ASN.1 encoder. Full host stays in SAN.
    if isinstance(name, bytes):
        name = name.decode('utf-8')
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name[:64])])


def _random_serial_number() -> int:
    # RFC 5280: serial must be positive and non-zero
    # 1 … 2⁶⁴-1
    serial_number = randbits(64)
    if serial_number <= 0:
        raise RuntimeError(f"Refusing to create a certificate with non-positive serial: {str(serial_number)}")
    return serial_number


def certificate_builder(
        subject: x509.Name,
        issuer: x509.Name,
        public_key,
        seconds_not_before: int = 0,
        seconds_not_after: int = certificates.SECONDS_NOT_AFTER_3_YEARS
) -> x509.CertificateBuilder:
    """Start a cryptography certificate (always X.509 v3) with a random serial, valid from now.

    :param subject: cryptography x509.Name of the certificate.
    :param issuer: cryptography x509.Name of the issuer; the subject itself for a self-signed certificate.
    :param public_key: cryptography public key the certificate is for.
    :param seconds_not_before: int, seconds from now when the certificate becomes valid. Probably should be 0.
    :param seconds_not_after: int, seconds from now when the certificate stops being valid.
    :return: cryptography x509.CertificateBuilder. Add extensions to it, then pass it to 'sign_certificate'.
    """

    now = datetime.now(timezone.utc).replace(microsecond=0)
    return (x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(public_key)
            .serial_number(_random_serial_number())
            .not_valid_before(now + timedelta(seconds=seconds_not_before))
            .not_valid_after(now + timedelta(seconds=seconds_not_after)))


def sign_certificate(builder: x509.CertificateBuilder, signing_key: crypto.PKey, hash_algo: str = 'sha256') -> crypto.X509:
    """Sign a cryptography certificate builder and return the certificate as pyOpenSSL X509 object.

    :param builder: cryptography x509.CertificateBuilder, e.g. from 'certificate_builder'.
    :param signing_key: pyOpenSSL private key of the issuer.
    :param hash_algo: string, hash algorithm. Default: 'sha256'.
    :return: certificate in pyOpenSSL x509 object.
    """

    certificate = builder.sign(signing_key.to_cryptography_key(), _hash_algorithm(hash_algo))
    return crypto.X509.from_cryptography(certificate)


def generate_certificate_signing_request(domain=None, certificate=None, key=None, hash_algo: str = 'sha256'):
    """Generate CSR - Certificate Signing Request.

    Using cryptography: pyOpenSSL 26.4.0 removed its X509Req.

    :param domain: domain name that will be used for CSR CN field.
        If 'certificate' and 'domain' are provided, 'domain' will be ignored.
    :param certificate: pyOpenSSL x509 certificate object. If provided, domain name will be taken from it.
        If 'certificate' and 'domain' are provided, 'domain' will be ignored.
    :param key: pyOpenSSL private key. If not provided, a new RSA 2048-bit key will be generated.
    :param hash_algo: string, hash algorithm. Default: 'sha256'.
    :return: tuple of the pyOpenSSL private key and the request,
        a cryptography x509.CertificateSigningRequest (was pyOpenSSL X509Req before 3.14.26).
    """

    if not domain and not certificate:
        raise ValueError('Either domain or certificate should be provided.')

    # If no key provided, generate a new one.
    if not key:
        key = generate_private_key()

    if not certificate:
        subject = name_from_common_name(domain)
    else:
        # Set the domain name from provided certificate.
        subject = name_from_common_name(certificate.get_subject().CN)

    csr_request = x509.CertificateSigningRequestBuilder().subject_name(subject).sign(
        key.to_cryptography_key(), _hash_algorithm(hash_algo))

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

    # RFC 5280: serial must be positive and non-zero
    # 1 … 2⁶⁴-1
    cert.set_serial_number(randbits(64))
    current_serial = cert.get_serial_number()
    if current_serial <= 0:
        raise RuntimeError(f"Refusing to create a certificate with non-positive serial: {str(current_serial)}")

    # X.520 ub-common-name (see generate_certificate_signing_request).
    cert.get_subject().CN = certname[:64]

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

    # The new key of the server certificate.
    key = generate_private_key()

    if certificate:
        # Re-sign the given certificate (e.g. one taken from the real server): it keeps its subject, serial,
        # validity and extensions, and gets the CA as issuer and the new key.
        server_certificate = certificate
        server_certificate.set_issuer(ca_cert.get_subject())
        server_certificate.set_pubkey(key)
        server_certificate.sign(ca_key, hash_algo)
        return server_certificate, key

    all_hosts = [x509.DNSName(host)]

    if wildcard:
        all_hosts += [x509.DNSName('*.' + host)]

    elif is_host_ip:
        all_hosts += [x509.IPAddress(ipaddress.ip_address(host))]

    all_hosts += [x509.IPAddress(ipaddress.ip_address(str(ip).strip())) for ip in cert_ips]
    all_hosts += [x509.DNSName(str(fqdn).strip()) for fqdn in cert_fqdns]

    builder = certificate_builder(
        subject=name_from_common_name(host),
        issuer=ca_cert.to_cryptography().subject,
        public_key=key.to_cryptography_key().public_key(),
        seconds_not_before=seconds_not_before,
        seconds_not_after=seconds_not_after)
    builder = builder.add_extension(x509.SubjectAlternativeName(all_hosts), critical=False)

    server_certificate = sign_certificate(builder, ca_key, hash_algo)
    return server_certificate, key


def convert_certificate_file_to_string(certificate_path: str):
    """Convert certificate to string.

    :param certificate_path: path to certificate.
    :return: certificate as string.
    """

    cert = crypto.load_certificate(crypto.FILETYPE_PEM, open(certificate_path).read())
    return crypto.dump_certificate(crypto.FILETYPE_TEXT, cert)

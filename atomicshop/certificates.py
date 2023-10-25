"""
Site for checking OIDs:
https://oidref.com/1.3.6.1.5.5.7.3.1
"""


import ssl

from .wrappers import cryptographyw
from .print_api import print_api


# Valid for 3 years from now
# Max validity is 39 months:
# https://casecurity.org/2015/02/19/ssl-certificate-validity-periods-limited-to-39-months-starting-in-april/
SECONDS_NOT_AFTER_3_YEARS = 3 * 365 * 24 * 60 * 60


def is_certificate_in_store(certificate, issuer_only: bool = False, thumbprint_only: bool = False):
    """
    The function will check if the certificate is installed in the Windows certificate store.

    :param certificate: x509 object, certificate to check.
    :param issuer_only: bool, if True, will check only by the certificate issuer common name is installed in the store.
        The problem that the issuer common name is not unique, so it can be installed multiple times.
    :param thumbprint_only: bool, if True, will check only by the certificate thumbprint is installed in the store.
        The problem that searching by the thumbprint will not tell you if there are multiple certificates with the same
        issuer name.
    :return: bool, True if certificate is installed, False if not.
    """

    # Make sure the certificate is x509.Certificate object.
    certificate = cryptographyw.convert_object_to_x509(certificate)
    # Get the certificate thumbprint.
    thumbprint = cryptographyw.get_sha1_thumbprint_from_x509(certificate)
    issuer_common_name: str = cryptographyw.get_issuer_common_name_from_x509(certificate)

    # for store in ["CA", "ROOT", "MY"]:
    for cert, encoding, trust in ssl.enum_certificates("ROOT"):
        store_certificate = cryptographyw.convert_object_to_x509(cert)
        store_issuer_common_name: str = cryptographyw.get_issuer_common_name_from_x509(store_certificate)
        store_thumbprint = cryptographyw.get_sha1_thumbprint_from_x509(store_certificate)

        if issuer_only:
            if store_issuer_common_name == issuer_common_name:
                return True, certificate
        elif thumbprint_only:
            if store_thumbprint == thumbprint:
                return True, certificate
        elif not issuer_only and not thumbprint_only:
            if store_thumbprint == thumbprint and store_issuer_common_name == issuer_common_name:
                return True, certificate


def get_certificates_by_issuer_name(issuer_name: str, print_kwargs: dict = None):
    """
    The function will return all certificates with the specified issuer name.

    :param issuer_name: string, issuer name to search for.
    :param print_kwargs: dict, that contains all the arguments for 'print_api' function.

    :return: list, of certificates with the specified issuer name.
    """

    if not print_kwargs:
        print_kwargs = {}

    certificates_list = []

    for cert, encoding, trust in ssl.enum_certificates("ROOT"):
        store_certificate = cryptographyw.convert_object_to_x509(cert)
        store_issuer_common_name: str = cryptographyw.get_issuer_common_name_from_x509(store_certificate)

        if store_issuer_common_name == issuer_name:
            certificates_list.append(store_certificate)

    if certificates_list:
        for certificate_single in certificates_list:
            issuer_name = cryptographyw.get_issuer_common_name_from_x509(certificate_single)
            thumbprint = cryptographyw.get_sha1_thumbprint_from_x509(certificate_single)
            message = f'Issuer name: {issuer_name} | Thumbprint: {thumbprint}'
            print_api(message, **print_kwargs)
    else:
        message = f'No certificates with issuer name: {issuer_name}'
        print_api(message, **print_kwargs)

    return certificates_list

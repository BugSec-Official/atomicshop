"""
Site for checking OIDs:
https://oidref.com/1.3.6.1.5.5.7.3.1
"""


import ssl
from typing import Literal

from .wrappers import cryptographyw
from .wrappers.pywin32w import cert_store
from .print_api import print_api


# Valid for 3 years from now
# Max validity is 39 months:
# https://casecurity.org/2015/02/19/ssl-certificate-validity-periods-limited-to-39-months-starting-in-april/
SECONDS_NOT_AFTER_3_YEARS = 3 * 365 * 24 * 60 * 60


def get_pem_certificate_from_string(certificate: str) -> str:
    """
    Some PEM certificates can contain a private key. This function will return only the certificate part.

    :param certificate: string, PEM certificate.
    :return: string, certificate part.
    """

    certificate_lines = certificate.split('\n')
    certificate_part = ''
    start = False
    for line in certificate_lines:
        if 'BEGIN CERTIFICATE' in line:
            start = True
        if start:
            certificate_part += line + '\n'
        if 'END CERTIFICATE' in line:
            break

    return certificate_part


def write_crt_certificate_file_in_pem_format_from_pem_file(
        pem_file_path: str,
        crt_file_path: str
):
    """
    The function will read the PEM certificate file and write it to the CRT file in PEM format.
    The function is used to convert the PEM certificate file to the CRT file.

    Basically the point here is that the CRT file is the same as the PEM file, but the extension is different,
    and it doesn't support integrated private key.

    :param pem_file_path: string, path to the PEM certificate file.
    :param crt_file_path: string, path to the CRT certificate file.
    """

    with open(pem_file_path, 'r') as f:
        certificate_string = f.read()

    certificate_pem = get_pem_certificate_from_string(certificate_string)

    with open(crt_file_path, 'w') as f:
        f.write(certificate_pem)


def is_certificate_in_store(
        certificate: any = None,
        by_cert_issuer: bool = True,
        by_cert_thumbprint: bool = True,
        issuer_name: str = None,
        store_location: str = "ROOT"
) -> tuple[bool, list]:
    """
    The function will check if the CA certificate is installed in the Windows certificate Trusted Root store.
    NO ADMIN RIGHTS NEEDED.

    :param certificate: x509 object, certificate to check. You can search by certificate or by issuer name.
        Supported types:
            string that is path to file will be imported as bytes object abd converted to x509.Certificate
                After check if it's PEM or DER format.
            string that is PEM certificate will be converted to bytes, then x509.Certificate
            bytes of PEM or DER will be converted to x509.Certificate.
            x509.Certificate will be returned as is.
    :param by_cert_issuer: bool, if True, will check only by the certificate issuer common name is installed in the store.
        The problem if the search will be by issuer alone, that the issuer common name is not unique,
        so it can be installed multiple times.
    :param by_cert_thumbprint: bool, if True, will check only by the certificate thumbprint is installed in the store.
        The problem that searching by the thumbprint alone will not tell you if there are multiple
        certificates with the same issuer name.
    :param issuer_name: string, issuer name to search for. You can search by certificate or by issuer name.
    :param store_location: string, store location to search in. Default is "ROOT".
    :return: tuple(bool - True if certificate is installed and False if not, list of certificates found)
    """

    if not by_cert_issuer and not by_cert_thumbprint:
        raise ValueError('At least one of the parameters "by_issuer" or "by_thumbprint" must be True.')

    if not certificate and not issuer_name:
        raise ValueError('At least one of the parameters "certificate" or "issuer_name" must be provided.')
    elif certificate and issuer_name:
        raise ValueError('Only one of the parameters "certificate" or "issuer_name" must be provided.')

    if certificate:
        # Make sure the certificate is x509.Certificate object.
        certificate_x509 = cryptographyw.convert_object_to_x509(certificate)
        # Get the certificate thumbprint.
        provided_thumbprint = cryptographyw.get_sha1_thumbprint_from_x509(certificate_x509)
        provided_issuer_common_name: str = cryptographyw.get_issuer_common_name_from_x509(certificate_x509)
    elif issuer_name:
        provided_thumbprint = None
        provided_issuer_common_name = issuer_name
    else:
        raise ValueError('At least one of the parameters "certificate" or "issuer_name" must be provided.')

    # Iterate over all certificates in the store specifically in the ROOT.
    # for store in ["CA", "ROOT", "MY"]:
    result_found_list: list = []
    found: bool = False
    for cert, encoding, trust in ssl.enum_certificates(store_location):
        store_certificate = cryptographyw.convert_object_to_x509(cert)
        store_issuer_common_name: str = cryptographyw.get_issuer_common_name_from_x509(store_certificate)
        store_thumbprint = cryptographyw.get_sha1_thumbprint_from_x509(store_certificate)

        if certificate:
            if by_cert_issuer and not by_cert_thumbprint:
                if store_issuer_common_name == provided_issuer_common_name:
                    result_found_list.append(store_certificate)
                    found = True
            elif by_cert_thumbprint and not by_cert_issuer:
                if store_thumbprint == provided_thumbprint:
                    result_found_list.append(store_certificate)
                    found = True
            elif by_cert_issuer and by_cert_thumbprint:
                if store_thumbprint == provided_thumbprint and store_issuer_common_name == provided_issuer_common_name:
                    result_found_list.append(store_certificate)
                    found = True
        elif issuer_name:
            if store_issuer_common_name == provided_issuer_common_name:
                result_found_list.append(store_certificate)
                found = True

    return found, result_found_list


def delete_certificate_by_issuer_name(
        issuer_name: str,
        store_location: Literal[
            "ROOT",
            "CA",
            "MY"] = "ROOT",
        print_kwargs: dict = None
):
    """
    NEED ADMIN RIGHTS.
    The function will remove all certificates with the specified issuer name.
    There can be several certificates with this name.

    :param issuer_name: string, issuer name to search for.
    :param store_location: string, store location to search in. Default is "ROOT".
    :param print_kwargs: dict, print_api kwargs.
    """

    cert_store.delete_certificate_by_issuer_name(issuer_name, store_location, print_kwargs)


def install_certificate_file(
        file_path: str,
        store_location: Literal[
            "ROOT", "CA", "MY"] = "ROOT",
        print_kwargs: dict = None
):
    """
    The function will install the certificate from the file to the specified store location.
    NEED ADMIN RIGHTS.

    :param file_path: string, full file path to the certificate file.
    :param store_location: string, store location to install the certificate. Default is "ROOT".
    :param print_kwargs: dict, print_api kwargs.
    """

    cert_store.install_certificate_file(file_path, store_location, print_kwargs)

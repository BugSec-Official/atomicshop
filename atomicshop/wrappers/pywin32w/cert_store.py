from typing import Literal
import win32crypt as wcrypt

from ...print_api import print_api
from ... import certificates


# lpszStoreProvider
CERT_STORE_PROV_SYSTEM = 0x0000000A
# dwFlags
CERT_SYSTEM_STORE_LOCAL_MACHINE = 0x00020000
CERT_SYSTEM_STORE_CURRENT_USER = 0x00010000
CERT_CLOSE_STORE_FORCE_FLAG = 0x00000001
CRYPT_STRING_BASE64HEADER = 0x00000000
X509_ASN_ENCODING = 0x00000001
CERT_STORE_ADD_REPLACE_EXISTING = 3


STORE_LOCATION_TO_CERT_SYSTEM_STORE: dict = {
    "ROOT": CERT_SYSTEM_STORE_LOCAL_MACHINE,
    "CA": CERT_SYSTEM_STORE_LOCAL_MACHINE,
    "MY": CERT_SYSTEM_STORE_CURRENT_USER
}


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

    """
    WinAPI doesn't like to do 2 actions in one iteration. So, first we will collect all certificates to remove,
    and in the second iteration remove them.
    
    Full Explanation:
    When you iterate with for cert in store.CertEnumCertificatesInStore(): and call 
    cert.CertDeleteCertificateFromStore() inside that loop, you’re modifying the underlying certificate store 
    while its internal enumeration is still active. This can lead to a segmentation fault (access violation 0xC0000005).
    By collecting the certificates in the first pass, you freeze the iteration so the store 
    doesn’t get mutated mid-enumeration.
    In the second pass, when you actually remove them, you’re no longer in the middle of enumerating. 
    This prevents the store’s pointer from becoming invalid.
    
    This approach should stop the Process finished with exit code -1073741819 (0xC0000005) issue.
    """

    store = wcrypt.CertOpenStore(
        CERT_STORE_PROV_SYSTEM,
        0,
        None,
        STORE_LOCATION_TO_CERT_SYSTEM_STORE[store_location],
        store_location
    )

    # Collect all matching certificates in a list
    certs_to_remove = []
    for cert in store.CertEnumCertificatesInStore():
        # Certificate properties.
        # cert.CertEnumCertificateContextProperties()
        subject_string: str = wcrypt.CertNameToStr(cert.Subject)
        if subject_string == issuer_name:
            # Remove the certificate.
            certs_to_remove.append(cert)

    # Remove all certificates from the list.
    for cert in certs_to_remove:
        cert.CertDeleteCertificateFromStore()
        print_api(f"Removed the Certificate from store [{store_location}] with issuer [{issuer_name}]", **(print_kwargs or {}))

    # There is an exception about store close.
    # store.CertCloseStore()


def install_certificate_file(
        file_path: str,
        store_location: Literal[
            "ROOT", "CA", "MY"] = "ROOT",
        print_kwargs: dict = None
):
    """
    NEED ADMIN RIGHTS.
    The function will install the certificate from the file to the specified store location.

    :param file_path: string, full file path to the certificate file.
    :param store_location: string, store location to install the certificate. Default is "ROOT".
    :param print_kwargs: dict, print_api kwargs.
    """

    with open(file_path, 'r') as f:
        certificate_string = f.read()

    certificate_pem = certificates.get_pem_certificate_from_string(certificate_string)

    certificate_bytes = wcrypt.CryptStringToBinary(certificate_pem, CRYPT_STRING_BASE64HEADER)[0]

    store = wcrypt.CertOpenStore(
        CERT_STORE_PROV_SYSTEM, 0, None, STORE_LOCATION_TO_CERT_SYSTEM_STORE[store_location], store_location)

    store.CertAddEncodedCertificateToStore(X509_ASN_ENCODING, certificate_bytes, CERT_STORE_ADD_REPLACE_EXISTING)
    store.CertCloseStore(CERT_CLOSE_STORE_FORCE_FLAG)

    message = f"Certificate installed to the store: [{store_location}] from file: [{file_path}]"
    print_api(message, **(print_kwargs or {}))

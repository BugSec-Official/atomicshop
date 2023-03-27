# v1.0.2 - 22.03.2021 - 11:10
import sys

from ..domains import get_domain_without_first_subdomain_if_no_subdomain_return_as_is
from ..print_api import print_api
from ..clones.certauth.certauth import CertificateAuthority

# External imports.
# Needed to read SAN (Subject Alternative Names) from certificate.
try:
    # noinspection PyPackageRequirements
    from cryptography import x509
except ImportError as exception_object:
    print(f"Library missing: {exception_object.name}. Install by executing: pip install cryptography")
    sys.exit()


def convert_list_of_domains_to_wildcarded(domain_list: list):
    domains_with_wildcards: list = list()

    # Add a wildcard to each domain.
    for domain in domain_list:
        # Extract parent domain from current domain.
        # Was using certauth function for it, but needed to rewrite it for offline usage.
        # parent_domain = certificate_object.get_wildcard_domain(domain)
        parent_domain = get_domain_without_first_subdomain_if_no_subdomain_return_as_is(domain)
        # Add regular parent domain to the list. Without it, it doesn't matter if there's wildcard or not. Wildcard
        # is used only for subdomains and not for parents.
        domains_with_wildcards.append(parent_domain)
        # And also Add wildcard domain to the list.
        domains_with_wildcards.append('*.' + parent_domain)

    return domains_with_wildcards


def extract_san_dns_entries_from_x509_certificate(open_ssl_x509):
    # Get created certificate as 'Certificate' object part of x509 of cryptography library.
    # 'open_ssl_x509' is 'OpenSSL.crypto.x509' object - the cert object itself.
    cryptography_certificate_object = open_ssl_x509.to_cryptography()
    # Get the extension of the certificate object and include only 'x509.SubjectAlternativeName'.
    san_extension_object = \
        cryptography_certificate_object.extensions.get_extension_for_class(x509.SubjectAlternativeName)
    # Get only the value of objects of SAN that contain 'DNSName' in them.
    san_dns_names_list_of_strings: list = san_extension_object.value.get_values_for_type(x509.DNSName)
    return san_dns_names_list_of_strings


class CertAuthWrapper:
    def __init__(self, ca_certificate_name, ca_certificate_filepath, server_certificate_directory):
        """
        :param ca_certificate_name:
        :param ca_certificate_filepath: string, full file path to CA certificate. If CA certificate is non-existent
            in this path, it will be created there.
        :param server_certificate_directory: string, full path to directory, where to store server certificate.
            If server certificate already exists it will be overwritten.
        """
        self.ca_certificate_name: str = ca_certificate_name
        self.ca_certificate_filepath: str = ca_certificate_filepath
        self.server_certificate_directory: str = server_certificate_directory

        # CertificateAuthority instance.
        self.cert_auth = None

    def create_use_ca_certificate(self):
        # Create certauth instance and CA certificate file.
        # If CA certificate is non-existent - it will not be overwritten,
        # but used to create the server certificate.
        # Full file paths for certificates should be used.
        # The CA file has to be ".pem" extension. The key and the certificate generated by certauth are included
        # in the same file. The private key is first and the certificate second.
        self.cert_auth = CertificateAuthority(
            self.ca_certificate_name, self.ca_certificate_filepath, cert_cache=self.server_certificate_directory)

    def create_overwrite_server_certificate_ca_signed(
            self, domains_with_wildcards: list, server_certificate_file_name_no_extension: str, **kwargs):
        server_certificate_tuple: tuple = tuple()

        # Create and overwrite existing certificate server file with all the 'domain_list'.
        # Basically 'cert_for_host()' function calls 'load_cert()' with 'include_cache_key=True'.
        # By default, 'load_cert()' returns '(cert, key)' tuple.
        # If 'include_cache_key=True' then cached key full file path
        # returned as third part of tuple '(cert, key, cache_key)'. And this 'cached_key' is what returned by
        # 'cert_for_host()' function.
        # Since we provide the 'overwrite=True', the default file will be overwritten.
        try:
            server_certificate_tuple = self.cert_auth.load_cert(
                server_certificate_file_name_no_extension,
                cert_fqdns=domains_with_wildcards,
                # wildcard_use_parent=True,
                # wildcard=True,
                include_cache_key=True,
                overwrite=True
            )
        except TypeError as function_exception_object:
            message = f'{function_exception_object}\n' \
                      f'Looks like you installed "certauth" from PyPi repository. ' \
                      f'Some functions are missing, try installing from git.'
            print_api(message, error_type=True, logger_method='critical_exception', **kwargs)
            pass

        return server_certificate_tuple

    def create_read_server_certificate_ca_signed(self, domain: str):
        # Same goes for service host certificate. "cert_for_host" creates new certificate with domain's name,
        # including subdomain, returns full path to that certificate as string.
        # If certificate file exists, the function will try to read it. If the format of certificate is wrong
        # or certificate is corrupted, an exception will be raised about it and no full path to certificate file
        # as string will be returned.
        server_certificate_file_path: str = self.cert_auth.cert_for_host(domain)

    # noinspection PyBroadException
    def create_overwrite_server_certificate_ca_signed_return_path_and_san(
            self,
            domain_list: list, server_certificate_file_name_no_extension: str,
            **kwargs):
        """
        Overwrites the default server certificate that will contain all the domains that the script extracted
        from engines 'engine_config.ini' file in 'domains' section and also all the new domains that were passed through
        SNI from Client Hello.

        :param domain_list: list, contains all the domains that are going to be processes with wildcards and added
            to server certificate.
        :param server_certificate_file_name_no_extension: string, name of server certificate that will be signed by CA.
            Also, will be used as file name for server certificate. '.pem' extension will be added by certauth.
        :type kwargs: object, will be passed to 'print_api'.
        :return: The path to the cached file.
        """

        # Setting locals.
        server_certificate_filepath: str = str()
        san_dns_names_list_of_strings: list = list()

        # Convert all the domains to parent domains with wildcards.
        domains_with_wildcards = convert_list_of_domains_to_wildcarded(domain_list)

        # Create CA certificate. If exists it will be used.
        self.create_use_ca_certificate()
        # Create or overwrite server certificate signed by the above CA certificate.
        server_certificate_tuple = self.create_overwrite_server_certificate_ca_signed(
            domains_with_wildcards=domains_with_wildcards,
            server_certificate_file_name_no_extension=server_certificate_file_name_no_extension
        )

        # If 'server_certificate_tuple' was successfully created.
        if server_certificate_tuple:
            # 'server_certificate_tuple[0]' is 'OpenSSL.crypto.x509' object - the cert object itself.
            # Get only the value of objects of SAN that contain 'DNSName' in them.
            san_dns_names_list_of_strings: list = extract_san_dns_entries_from_x509_certificate(
                server_certificate_tuple[0])

            # Taking only the 'cache_key' full file path, which is the third entry in the 'server_certificate_tuple'.
            server_certificate_filepath = server_certificate_tuple[2]

        return server_certificate_filepath, san_dns_names_list_of_strings

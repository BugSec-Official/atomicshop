import os
import sys

from cryptography import x509

from . import creator, socket_base, socket_client
from .. import pyopensslw, cryptographyw
from ..certauthw.certauthw import CertAuthWrapper
from ...print_api import print_api
from ... import filesystem


class Certificator:
    """
    Certificator class is used to create and manage certificates, wrapping ssl contexts and sockets.
    """
    def __init__(
            self,
            ca_certificate_name: str,
            ca_certificate_filepath: str,
            default_server_certificate_usage: bool,
            default_server_certificate_name: str,
            default_server_certificate_directory: str,
            default_certificate_domain_list: list,
            sni_server_certificates_cache_directory: str,
            sni_get_server_certificate_from_server_socket: bool,
            sni_server_certificate_from_server_socket_download_directory: str,
            custom_server_certificate_usage: bool,
            custom_server_certificate_path: str,
            custom_private_key_path: str,
            forwarding_dns_service_ipv4_list___only_for_localhost: list,
            skip_extension_id_list: list,
            tls: bool,
            enable_sslkeylogfile_env_to_client_ssl_context: bool,
            sslkeylog_file_path: str
    ):
        self.ca_certificate_name = ca_certificate_name
        self.ca_certificate_filepath = ca_certificate_filepath
        self.default_server_certificate_usage = default_server_certificate_usage
        self.default_server_certificate_name = default_server_certificate_name
        self.default_server_certificate_directory = default_server_certificate_directory
        self.default_certificate_domain_list = default_certificate_domain_list
        self.sni_server_certificates_cache_directory = sni_server_certificates_cache_directory
        self.sni_get_server_certificate_from_server_socket = sni_get_server_certificate_from_server_socket
        self.sni_server_certificate_from_server_socket_download_directory = (
            sni_server_certificate_from_server_socket_download_directory)
        self.custom_server_certificate_usage = custom_server_certificate_usage
        self.custom_server_certificate_path = custom_server_certificate_path
        self.custom_private_key_path = custom_private_key_path
        self.forwarding_dns_service_ipv4_list___only_for_localhost = (
            forwarding_dns_service_ipv4_list___only_for_localhost)
        self.skip_extension_id_list = skip_extension_id_list
        self.tls = tls
        self.enable_sslkeylogfile_env_to_client_ssl_context: bool = (
            enable_sslkeylogfile_env_to_client_ssl_context)
        self.sslkeylog_file_path: str = sslkeylog_file_path

        # noinspection PyTypeChecker
        self.certauth_wrapper: CertAuthWrapper = None

    def initialize_certauth_create_use_ca_certificate(self, server_certificate_directory: str):
        """
        Initialize CertAuthWrapper and create CA certificate if it doesn't exist.
        :return:
        """
        # Initialize CertAuthWrapper.
        certauth_wrapper = CertAuthWrapper(
            ca_certificate_name=self.ca_certificate_name,
            ca_certificate_filepath=self.ca_certificate_filepath,
            server_certificate_directory=server_certificate_directory
        )

        # Create CA certificate if it doesn't exist.
        certauth_wrapper.create_use_ca_certificate()

        return certauth_wrapper

    # noinspection PyTypeChecker
    def select_server_ssl_context_certificate(
            self,
            print_kwargs: dict = None
    ):
        """
        This function selects between the default certificate and custom certificate for the sll context.
        Returns the selected certificate file path and the private key file path.
        """
        # We need to nullify the variable, since we have several checks if the variable was set or not.
        server_certificate_file_path: str = None
        server_private_key_file_path: str = None

        # Creating if non-existent/overwriting default server certificate.
        if self.default_server_certificate_usage:
            # Creating if non-existent/overwriting default server certificate.
            server_certificate_file_path, default_server_certificate_san = \
                self.create_overwrite_default_server_certificate_ca_signed()

            # Check if default certificate was created.
            if server_certificate_file_path:
                message = f"Default Server Certificate was created / overwritten: {server_certificate_file_path}"
                print_api(message, **(print_kwargs or {}))

                message = \
                    f"Default Server Certificate current 'Subject Alternative Names': {default_server_certificate_san}"
                print_api(message, **(print_kwargs or {}))
            else:
                message = f"Couldn't create / overwrite Default Server Certificate: {server_certificate_file_path}"
                print_api(message, error_type=True, logger_method='critical', **(print_kwargs or {}))
                sys.exit()

        # Assigning 'certificate_path' to 'custom_certificate_path' if usage was set.
        if self.custom_server_certificate_usage:
            server_certificate_file_path = self.custom_server_certificate_path
            # Since 'ssl_context.load_cert_chain' uses 'keypath' as 'None' if certificate contains private key.
            # We'd like to leave it that way and don't fetch empty string from 'config'.
            if self.custom_private_key_path:
                server_private_key_file_path = self.custom_private_key_path

        return server_certificate_file_path, server_private_key_file_path

    def create_overwrite_default_server_certificate_ca_signed(self):
        """
        Create or overwrite default server certificate.
        :return:
        """

        self.certauth_wrapper = self.initialize_certauth_create_use_ca_certificate(
            server_certificate_directory=self.default_server_certificate_directory
        )

        server_certificate_file_name_no_extension = self.default_server_certificate_name

        server_certificate_file_path, default_server_certificate_san = \
            self.certauth_wrapper.create_overwrite_server_certificate_ca_signed_return_path_and_san(
                domain_list=self.default_certificate_domain_list,
                server_certificate_file_name_no_extension=server_certificate_file_name_no_extension
            )

        return server_certificate_file_path, default_server_certificate_san

    def create_use_sni_server_certificate_ca_signed(
            self,
            sni_received_parameters,
            print_kwargs: dict = None
    ):
        # === Connect to the domain and get the certificate. ===========================================================
        certificate_from_socket_x509 = None
        if self.sni_get_server_certificate_from_server_socket:
            # Generate PEM certificate file path string for downloaded certificates. Signed certificates will go to the
            # 'certs' folder.
            certificate_from_socket_file_path: str = \
                self.sni_server_certificate_from_server_socket_download_directory + \
                os.sep + sni_received_parameters.destination_name + ".pem"
            # Get client ip.
            client_ip = socket_base.get_source_address_from_socket(sni_received_parameters.ssl_socket)[0]

            # If we're on localhost, then use external services list in order to resolve the domain:
            if client_ip in socket_base.THIS_DEVICE_IP_LIST:
                service_client = socket_client.SocketClient(
                    service_name=sni_received_parameters.destination_name,
                    service_port=socket_base.get_destination_address_from_socket(sni_received_parameters.ssl_socket)[1],
                    tls=self.tls,
                    dns_servers_list=self.forwarding_dns_service_ipv4_list___only_for_localhost,
                    logger=print_kwargs.get('logger') if print_kwargs else None
                )
            # If we're not on localhost, then connect to domain directly.
            else:
                service_client = socket_client.SocketClient(
                    service_name=sni_received_parameters.destination_name,
                    service_port=socket_base.get_destination_address_from_socket(sni_received_parameters.ssl_socket)[1],
                    tls=self.tls,
                    logger=print_kwargs.get('logger') if print_kwargs else None
                )

            # If certificate from socket exists, then we don't need to get it from the socket and write to file.
            # and we will return None, since no certificate was fetched.
            # noinspection PyTypeChecker
            certificate_from_socket_x509_cryptography_object: x509.Certificate = None
            if not filesystem.is_file_exists(certificate_from_socket_file_path):
                print_api("Certificate from socket doesn't exist, fetching.", **(print_kwargs or {}))
                # Get certificate from socket and convert to X509 cryptography module object.
                certificate_from_socket_x509_cryptography_object: x509.Certificate = (
                    service_client.get_certificate_from_server(
                        save_as_file=True, cert_file_path=certificate_from_socket_file_path,
                        cert_output_type='cryptography')
                )
            else:
                print_api("The Certificate from socket already exists, not fetching", **(print_kwargs or {}))
                certificate_from_socket_x509_cryptography_object: x509.Certificate = (
                    cryptographyw.convert_object_to_x509(certificate_from_socket_file_path))

            # skip_extensions = ['1.3.6.1.5.5.7.3.2', '2.5.29.31', '1.3.6.1.5.5.7.1.1']

            # If certificate was downloaded successfully, then remove extensions if they were provided.
            # If certificate was downloaded successfully and no extensions to skip were provided, then use it as is.
            if certificate_from_socket_x509_cryptography_object and self.skip_extension_id_list:
                # Copy extensions from old certificate to new certificate, without specified extensions.
                certificate_from_socket_x509_cryptography_object, _ = \
                    cryptographyw.copy_extensions_from_old_cert_to_new_cert(
                        certificate_from_socket_x509_cryptography_object,
                        skip_extensions=self.skip_extension_id_list,
                        print_kwargs=print_kwargs
                    )

            # If certificate was downloaded successfully, then convert it to pyopenssl object.
            if certificate_from_socket_x509_cryptography_object:
                # Convert X509 cryptography module object to pyopenssl, since certauth uses pyopenssl.
                certificate_from_socket_x509 = \
                    pyopensslw.convert_cryptography_object_to_pyopenssl(
                        certificate_from_socket_x509_cryptography_object)

        # === EOF Get certificate from the domain. =====================================================================

        # If CertAuthWrapper wasn't initialized yet, it means that CA wasn't created/loaded yet.
        if not self.certauth_wrapper:
            self.certauth_wrapper = self.initialize_certauth_create_use_ca_certificate(
                server_certificate_directory=self.sni_server_certificates_cache_directory)
        # try:
        # Create if non-existent / read existing server certificate.
        sni_server_certificate_file_path = self.certauth_wrapper.create_read_server_certificate_ca_signed(
            sni_received_parameters.destination_name, certificate_from_socket_x509)

        message = f"SNI Handler: port " \
                  f"{socket_base.get_destination_address_from_socket(sni_received_parameters.ssl_socket)[1]}: " \
                  f"Using certificate: {sni_server_certificate_file_path}"
        print_api(message, **print_kwargs)

        # You need to build new context and exchange the context that being inherited from the main socket,
        # or else the context will receive previous certificate each time.
        sni_received_parameters.ssl_socket.context = (
            creator.create_server_ssl_context___load_certificate_and_key(
                certificate_file_path=sni_server_certificate_file_path, key_file_path=None,
                enable_sslkeylogfile_env_to_client_ssl_context=self.enable_sslkeylogfile_env_to_client_ssl_context,
                sslkeylog_file_path=self.sslkeylog_file_path
            )
        )

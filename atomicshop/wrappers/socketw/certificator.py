import os
import sys

from cryptography import x509

from . import creator, socket_base, ssl_base
from .. import pyopensslw, cryptographyw
from ..certauthw.certauthw import CertAuthWrapper
from ...print_api import print_api
from ... import filesystem
from ...file_io import file_io


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
            reuse_server_socket_certificate: bool,
            reuse_server_socket_certificate_download_directory: str,
            custom_server_certificate_usage: bool,
            custom_server_certificate_path: str,
            custom_private_key_path: str,
            skip_extension_id_list: list,
            enable_sslkeylogfile_env_to_client_ssl_context: bool,
            sslkeylog_file_path: str,
            server_alpn_protocols: list[str] | None = None,
            origin_socket_client=None
    ):
        self.ca_certificate_name = ca_certificate_name
        self.ca_certificate_filepath = ca_certificate_filepath
        self.default_server_certificate_usage = default_server_certificate_usage
        self.default_server_certificate_name = default_server_certificate_name
        self.default_server_certificate_directory = default_server_certificate_directory
        self.default_certificate_domain_list = default_certificate_domain_list
        self.sni_server_certificates_cache_directory = sni_server_certificates_cache_directory
        self.reuse_server_socket_certificate = reuse_server_socket_certificate
        self.reuse_server_socket_certificate_download_directory = (
            reuse_server_socket_certificate_download_directory)
        self.custom_server_certificate_usage = custom_server_certificate_usage
        self.custom_server_certificate_path = custom_server_certificate_path
        self.custom_private_key_path = custom_private_key_path
        self.skip_extension_id_list = skip_extension_id_list
        self.enable_sslkeylogfile_env_to_client_ssl_context: bool = (
            enable_sslkeylogfile_env_to_client_ssl_context)
        self.sslkeylog_file_path: str = sslkeylog_file_path
        self.server_alpn_protocols = server_alpn_protocols
        self.origin_socket_client = origin_socket_client

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
        # === Clone the certificate from the reused origin socket. =====================================================
        certificate_from_socket_x509 = None
        if self.reuse_server_socket_certificate and self.origin_socket_client is not None:
            certificate_from_socket_file_path: str = (
                self.reuse_server_socket_certificate_download_directory + os.sep
                + sni_received_parameters.destination_name + ".pem")

            # noinspection PyTypeChecker
            certificate_from_socket_x509_cryptography_object: x509.Certificate = None
            if not filesystem.is_file_exists(certificate_from_socket_file_path):
                print_api("Certificate from socket doesn't exist, cloning from the live origin socket.",
                          **(print_kwargs or {}))
                # DER off the already-connected data socket — no new connection, socket stays alive.
                der = self.origin_socket_client.get_peer_certificate_der()
                certificate_from_socket_x509_cryptography_object = cryptographyw.convert_der_to_x509_object(der)
                pem_string = ssl_base.convert_der_x509_bytes_to_pem_string(der)
                file_io.write_file(pem_string, file_path=certificate_from_socket_file_path)
            else:
                print_api("The Certificate from socket already exists, not fetching", **(print_kwargs or {}))
                certificate_from_socket_x509_cryptography_object = \
                    cryptographyw.convert_object_to_x509(certificate_from_socket_file_path)

            if certificate_from_socket_x509_cryptography_object and self.skip_extension_id_list:
                certificate_from_socket_x509_cryptography_object, _ = \
                    cryptographyw.copy_extensions_from_old_cert_to_new_cert(
                        certificate_from_socket_x509_cryptography_object,
                        skip_extensions=self.skip_extension_id_list,
                        print_kwargs=print_kwargs)

            if certificate_from_socket_x509_cryptography_object:
                certificate_from_socket_x509 = pyopensslw.convert_cryptography_object_to_pyopenssl(
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

        # ``raw_socket`` is used here rather than ``ssl_socket`` because the
        # BIO accept path's ``ssl_socket`` is an ``SSLObject`` with no
        # ``getsockname`` — the raw TCP socket is the source of address info.
        message = f"SNI Handler: port " \
                  f"{socket_base.get_destination_address_from_socket(sni_received_parameters.raw_socket)[1]}: " \
                  f"Using certificate: {sni_server_certificate_file_path}"
        print_api(message, **print_kwargs)

        # You need to build new context and exchange the context that being inherited from the main socket,
        # or else the context will receive previous certificate each time.
        # ``alpn_protocols`` must be re-asserted on the swapped context — ``set_alpn_protocols``
        # is write-only with no inheritance, so omitting it here drops ALPN from ServerHello.
        # ``inherit_from`` carries cipher policy across the swap (see ``copy_server_ctx_settings``).
        sni_received_parameters.ssl_socket.context = (
            creator.create_server_ssl_context___load_certificate_and_key(
                certificate_file_path=sni_server_certificate_file_path, key_file_path=None,
                inherit_from=sni_received_parameters.ssl_socket.context,
                enable_sslkeylogfile_env_to_client_ssl_context=self.enable_sslkeylogfile_env_to_client_ssl_context,
                sslkeylog_file_path=self.sslkeylog_file_path,
                alpn_protocols=self.server_alpn_protocols,
            )
        )

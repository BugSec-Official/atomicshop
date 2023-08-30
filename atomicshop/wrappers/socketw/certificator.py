import os
import sys

from . import creator, base, socket_client
from .. import pyopensslw, cryptographyw
from ..certauthw.certauthw import CertAuthWrapper
from ...print_api import print_api


# noinspection PyTypeChecker
CERTAUTH_WRAPPER: CertAuthWrapper = None


def initialize_certauth_create_use_ca_certificate(config: dict):
    # Initialize CertAuthWrapper.
    if config['certificates']['default_server_certificate_usage']:
        server_certificate_directory = config['certificates']['default_server_certificate_directory']
    else:
        server_certificate_directory = config['certificates']['sni_server_certificates_cache_directory']

    certauth_wrapper = CertAuthWrapper(
        ca_certificate_name=config['certificates']['ca_certificate_name'],
        ca_certificate_filepath=config['certificates']['ca_certificate_filepath'],
        server_certificate_directory=server_certificate_directory
    )

    # Create CA certificate if it doesn't exist.
    certauth_wrapper.create_use_ca_certificate()

    return certauth_wrapper


# noinspection PyTypeChecker
def select_server_ssl_context_certificate(config: dict, print_kwargs: dict = None):
    # We need to nullify the variable, since we have several checks if the variable was set or not.
    server_certificate_file_path: str = None
    server_private_key_file_path: str = None

    # Creating if non-existent/overwriting default server certificate.
    # 'server_certificate_filepath' will be assigned there.
    if config['certificates']['default_server_certificate_usage']:
        server_certificate_file_path, default_server_certificate_san = \
            create_overwrite_default_server_certificate_ca_signed(config=config)

        # Check if default certificate was created.
        if server_certificate_file_path:
            message = f"Default Server Certificate was created / overwritten: {server_certificate_file_path}"
            print_api(message, **print_kwargs)

            message = \
                f"Default Server Certificate current 'Subject Alternative Names': {default_server_certificate_san}"
            print_api(message, **print_kwargs)
        else:
            message = f"Couldn't create / overwrite Default Server Certificate: {server_certificate_file_path}"
            print_api(message, error_type=True, logger_method='critical', **print_kwargs)
            sys.exit()

        # Assigning 'certificate_path' to 'custom_certificate_path' if usage was set.
        if config['certificates']['custom_server_certificate_usage']:
            server_certificate_file_path = config['certificates']['custom_server_certificate_path']
            # Since 'ssl_context.load_cert_chain' uses 'keypath' as 'None' if certificate contains private key.
            # We'd like to leave it that way and don't fetch empty string from 'config'.
            if config['certificates']['custom_private_key_path']:
                server_private_key_file_path = config['certificates']['custom_private_key_path']

    return server_certificate_file_path, server_private_key_file_path


def create_overwrite_default_server_certificate_ca_signed(config: dict):
    global CERTAUTH_WRAPPER
    CERTAUTH_WRAPPER = initialize_certauth_create_use_ca_certificate(config=config)

    domain_list = config['certificates']['domains_all_times']
    server_certificate_file_name_no_extension = config['certificates']['default_server_certificate_name']

    server_certificate_file_path, default_server_certificate_san = \
        CERTAUTH_WRAPPER.create_overwrite_server_certificate_ca_signed_return_path_and_san(
            domain_list=domain_list,
            server_certificate_file_name_no_extension=server_certificate_file_name_no_extension
        )

    return server_certificate_file_path, default_server_certificate_san


def create_use_sni_server_certificate_ca_signed(sni_received_dict: dict, config: dict, print_kwargs: dict = None):
    global CERTAUTH_WRAPPER

    # === Connect to the domain and get the certificate. ===========================================================
    certificate_from_socket_x509 = None
    if config['certificates']['sni_get_server_certificate_from_server_socket']:
        # Generate PEM certificate file path string for downloaded certificates. Signed certificates will go to the
        # 'certs' folder.
        certificate_from_socket_file_path: str = \
            config['certificates']['sni_server_certificate_from_server_socket_download_directory'] + \
            os.sep + sni_received_dict['destination_name'] + ".pem"
        # Get client ip.
        client_ip = base.get_source_address_from_socket(sni_received_dict['ssl_socket'])[0]

        # If we're on localhost, then use external services list in order to resolve the domain:
        if client_ip == "127.0.0.1":
            service_client = socket_client.SocketClient(
                service_name=sni_received_dict['destination_name'],
                service_port=base.get_destination_address_from_socket(sni_received_dict['ssl_socket'])[1],
                dns_servers_list=config['tcp']['forwarding_dns_service_ipv4_list___only_for_localhost'])
        # If we're not on localhost, then connect to domain directly.
        else:
            service_client = socket_client.SocketClient(
                service_name=sni_received_dict['destination_name'],
                service_port=base.get_destination_address_from_socket(sni_received_dict['ssl_socket'])[1])

        # Get certificate from socket and convert to X509 cryptography module object.
        certificate_from_socket_x509_cryptography_object = service_client.get_certificate_from_server(
            save_as_file=True, cert_file_path=certificate_from_socket_file_path, cert_output_type='cryptography'
        )

        # skip_extensions = ['1.3.6.1.5.5.7.3.2', '2.5.29.31', '1.3.6.1.5.5.7.1.1']

        # If certificate was downloaded successfully, then remove extensions if they were provided.
        # If certificate was downloaded successfully and no extensions to skip were provided, then use it as is.
        if certificate_from_socket_x509_cryptography_object and config['skip_extensions']:
            # Copy extensions from old certificate to new certificate, without specified extensions.
            certificate_from_socket_x509_cryptography_object, _ = \
                cryptographyw.copy_extensions_from_old_cert_to_new_cert(
                    certificate_from_socket_x509_cryptography_object,
                    skip_extensions=config['skip_extensions'],
                    print_kwargs=print_kwargs
                )

        # If certificate was downloaded successfully, then convert it to pyopenssl object.
        if certificate_from_socket_x509_cryptography_object:
            # Convert X509 cryptography module object to pyopenssl, since certauth uses pyopenssl.
            certificate_from_socket_x509 = \
                pyopensslw.convert_cryptography_object_to_pyopenssl(certificate_from_socket_x509_cryptography_object)

    # === EOF Get certificate from the domain. =====================================================================

    # If CertAuthWrapper wasn't initialized yet, it means that CA wasn't created/loaded yet.
    if not CERTAUTH_WRAPPER:
        CERTAUTH_WRAPPER = initialize_certauth_create_use_ca_certificate(config=config)
    # try:
    # Create if non-existent / read existing server certificate.
    sni_server_certificate_file_path = CERTAUTH_WRAPPER.create_read_server_certificate_ca_signed(
        sni_received_dict['destination_name'], certificate_from_socket_x509)

    message = f"SNI Handler: port " \
              f"{base.get_destination_address_from_socket(sni_received_dict['ssl_socket'])[1]}: " \
              f"Using certificate: {sni_server_certificate_file_path}"
    print_api(message, **print_kwargs)

    # except Exception as e:
    #     message = \
    #         f"SNI Handler: Undocumented exception while creating / using certificate for a domain: {e}"
    #     print_api(
    #         message, error_type=True, logger_method="critical", traceback_string=True, oneline=True,
    #         logger=self.logger)
    #     pass

    # try:
    # You need to build new context and exchange the context that being inherited from the main socket,
    # or else the context will receive previous certificate each time.
    sni_received_dict['ssl_socket'].context = \
        creator.create_server_ssl_context___load_certificate_and_key(sni_server_certificate_file_path, None)
    # except Exception as e:
    #     message = \
    #         f"SNI Handler: Undocumented exception while creating and assigning new SSLContext: {e}"
    #     print_api(
    #         message, error_type=True, logger_method="critical", traceback_string=True, oneline=True,
    #         logger=self.logger)
    #     pass

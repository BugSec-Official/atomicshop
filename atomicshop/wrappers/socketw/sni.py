import sys
import ssl

from . import certificator, creator
from ...domains import get_domain_without_first_subdomain_if_no_subdomain_return_as_is
from ...print_api import print_api


def add_sni_callback_function_reference_to_ssl_context(
        ssl_context, config: dict, dns_domain: str = None,
        sni_function_name=None, use_default_sni_function: bool = False, use_sni_extended: bool = False,
        print_kwargs: dict = None):
    """
    Add SNI callback function reference to SSLContext object. Inplace.

    :param ssl_context:
    :param config:
    :param dns_domain: domain that was received from DNS Server that will be used if no SNI was passed.
    :param sni_function_name: Reference to the function that will be called when SNI is present in the request.
    :param use_default_sni_function: If True, will use default SNI function.
    :param use_sni_extended: If True, will use extended SNI function.
    :param print_kwargs: dict, that contains all the arguments for 'print_api' function.
    :return:
    """

    if sni_function_name and (use_default_sni_function or use_sni_extended):
        raise ValueError("You can't use both custom and default SNI function at the same time.")

    if use_sni_extended and not use_default_sni_function:
        raise ValueError("You can't use extended SNI function without default SNI function.")

    # SNI - Server Name Indication: https://en.wikipedia.org/wiki/Server_Name_Indication
    # SNI is extension to TLS protocol to tell the Server what is destination domain that the client is trying to
    # connect. The server knowing the destination domain then can present to the client the appropriate certificate.
    # "sni_callback" method: https://docs.python.org/3/library/ssl.html#ssl.SSLContext.sni_callback
    # The method calls your custom function. If there is SNI present in the TLS request from the client, then the
    # function will be called. Automatically providing 3 parameters from the system: ssl.SSLSocket, The destination
    # server name, current ssl.SSLContext object.
    # If you check the custom function it has all these variables mandatory, since this is what system provides and
    # handled by the system, if SNI is existent.
    # The function is actually called at "accept()" method of the "ssl.SSLSocket"
    # This needs to be set only once on the listening socket
    if sni_function_name:
        ssl_context.sni_callback = sni_function_name

    if use_default_sni_function:
        ssl_context.set_servername_callback(
            setup_sni_callback(
                use_sni_extended=use_sni_extended, config=config, dns_domain=dns_domain, print_kwargs=print_kwargs)
        )


# Server Name Indication (SNI) is an extension to the Transport Layer Security (TLS) computer networking protocol.
# Function to handle server's SSLContext's SNI callback function.
# This is actually called first during "accept()" method of the "ssl.SSLSocket" then comes accept itself.
# This happens in 'ssl.py' module in 'self._sslobj.do_handshake()' function.
def setup_sni_callback(
        use_sni_extended: bool = False, config: dict = None, dns_domain: str = None, print_kwargs: dict = None):
    """
    Setup SNI callback function.
    :param use_sni_extended: Use extended SNI function, besides the default one.
    :param config:
    :param dns_domain: domain that was received from DNS Server that will be used if no SNI was passed.
    :param print_kwargs: dict, that contains all the arguments for 'print_api' function.
    :return:
    """

    def sni_handle(
            sni_ssl_socket: ssl.SSLSocket,
            sni_destination_name: str,
            sni_ssl_context: ssl.SSLContext):

        if use_sni_extended and not config:
            raise ValueError("You can't use extended SNI function without config.")

        sni_received_dict = {
            'ssl_socket': sni_ssl_socket,
            'destination_name': sni_destination_name,
            'ssl_context': sni_ssl_context
        }

        # If 'sni_execute_extended' was set to True.
        if use_sni_extended:
            sni_handle_extended(sni_received_dict, config=config, dns_domain=dns_domain, print_kwargs=print_kwargs)
        # Just set the server_hostname in current socket.
        else:
            sni_received_dict['ssl_socket'].server_hostname = sni_destination_name
    return sni_handle


def sni_handle_extended(sni_received_dict: dict, config: dict, dns_domain: str = None, print_kwargs: dict = None):
    # Set 'server_hostname' for the socket.
    set_socket_server_hostname(sni_received_dict=sni_received_dict, dns_domain=dns_domain, print_kwargs=print_kwargs)

    # If 'sni_default_server_certificates_addons' was set to 'True' in the 'config.ini'.
    # This section will add all the new domains that hit the server to default certificate SAN with wildcard.
    if config['certificates']['sni_default_server_certificate_addons']:
        sni_add_domain_to_default_server_certificate(sni_received_dict=sni_received_dict, config=config,
                                                     print_kwargs=print_kwargs)

    # If SNI server certificate creation was set to 'True', we'll create certificate for each incoming domain if
    # non-existent in certificates cache folder.
    if config['certificates']['sni_create_server_certificate_for_each_domain']:
        certificator.create_use_sni_server_certificate_ca_signed(
            sni_received_dict=sni_received_dict, config=config, print_kwargs=print_kwargs)


def set_socket_server_hostname(sni_received_dict: dict, dns_domain: str = None, print_kwargs: dict = None):
    service_name_from_sni = None

    # Try on general settings in the SNI function.
    try:
        # Check if SNI was passed.
        if sni_received_dict['destination_name']:
            service_name_from_sni = sni_received_dict['destination_name']
        # If no SNI was passed.
        else:
            # If DNS server is enabled we'll get the domain from dns server.
            if dns_domain:
                service_name_from_sni = dns_domain
                message = f"SNI Handler: No SNI was passed, using domain from DNS Server: {service_name_from_sni}"
                print_api(message, **print_kwargs)
            # If DNS server is disabled, the domain from dns server will be empty.
            else:
                message = f"SNI Handler: No SNI was passed, No domain passed from DNS Server. " \
                            f"Service name will be 'None'."
                print_api(message, **print_kwargs)

        # Setting "server_hostname" as a domain.
        sni_received_dict['ssl_socket'].server_hostname = service_name_from_sni
        message = \
            f"SNI Handler: port {sni_received_dict['ssl_socket'].getsockname()[1]}: " \
            f"Incoming connection for [{sni_received_dict['ssl_socket'].server_hostname}]"
        print_api(message, **print_kwargs)
    except Exception as exception_object:
        message = f"SNI Handler: Undocumented exception general settings section: {exception_object}"
        print_api(message, error_type=True, logger_method="error", traceback_string=True, oneline=True,
                  **print_kwargs)
        pass


def sni_add_domain_to_default_server_certificate(sni_received_dict: dict, config: dict, print_kwargs: dict = None):
    # Check if incoming domain is already in the parent domains of 'domains_all_times' list.
    if not any(x in sni_received_dict['ssl_socket'].server_hostname for x in
               config['certificates']['domains_all_times']):
        message = f"SNI Handler: Current domain is not in known domains list. Adding."
        print_api(message, **print_kwargs)
        # In the past was using 'certauth' to extract tlds, but it works only in online mode, so rewrote
        # the function to disable online fetching of TLD snapshot.
        # Initialize 'certauth' object.
        # certificate_object = CertificateAuthority(certificate_ca_name, certificate_ca_filepath)
        # Extract parent domain from the current SNI domain.
        # parent_domain = certificate_object.get_wildcard_domain(service_name_from_sni)

        # Extract parent domain from the current SNI domain.
        parent_domain = get_domain_without_first_subdomain_if_no_subdomain_return_as_is(
            sni_received_dict['ssl_socket'].server_hostname)
        # Add the parent domain to the known domains list.
        config['certificates']['domains_all_times'].append(parent_domain)

        default_server_certificate_path, subject_alternate_names = \
            certificator.create_overwrite_default_server_certificate_ca_signed(config=config)

        if default_server_certificate_path:
            message = f"SNI Handler: Default Server Certificate was created / overwritten: " \
                        f"{default_server_certificate_path}"
            print_api(message, **print_kwargs)

            message = f"SNI Handler: Server Certificate current 'Subject Alternative Names': " \
                      f"{subject_alternate_names}"
            print_api(message, **print_kwargs)

            # Since new default certificate was created we need to create new SSLContext and add the certificate.
            # You need to build new context and exchange the context that being inherited from the main socket,
            # or else the context will receive previous certificate each time.
            sni_received_dict['ssl_socket'].context = \
                creator.create_server_ssl_context___load_certificate_and_key(default_server_certificate_path, None)
        else:
            message = f"Couldn't create / overwrite Default Server Certificate: {default_server_certificate_path}"
            print_api(message, error_type=True, logger_method="critical", **print_kwargs)
            sys.exit()

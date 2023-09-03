import socket
import ssl

from . import base, sni, certificator, exception_wrapper
from ...print_api import print_api


def create_socket_ipv4_tcp():
    # When using 'with' statement, no need to use "socket.close()" method to disconnect when finished
    # AF_INET - Socket family of IPv4
    # SOCK_STREAM - Socket type of TCP
    return socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def add_reusable_address_option(socket_instance):
    # "setsockopt" is a method that can add options to the socket. Not needed for regular connection,
    # but for some types of protocols that come after that.
    # SOL_SOCKET - the "level", constant that contains the "SP_REUSEADDR"
    # SO_REUSEADDR - permit reuse of local addresses for this socket. If you enable this option, you can actually
    # have two sockets with the same Internet port number. Needed for protocols that force you to use the same port.
    # 1 - Sets this to true
    # For more options of this constant:
    # https://www.gnu.org/software/libc/manual/html_node/Socket_002dLevel-Options.html#Socket_002dLevel-Options
    socket_instance.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


def create_ssl_context_for_server():
    # Creating context with SSL certificate and the private key before the socket
    # https://docs.python.org/3/library/ssl.html
    # Creating context for SSL wrapper, specifying "PROTOCOL_TLS_SERVER" will pick the best TLS version protocol for
    # the server.
    return ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    # return ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)


def create_ssl_context_for_client():
    return ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


def set_client_ssl_context_default_certs(ssl_context):
    # "load_default_certs" method is telling the client to check the local certificate storage on the system for the
    # needed certificate of the server. Without this line you will get an error from the server that the client
    # is using self-signed certificate. Which is partly true, since you used the SLL wrapper,
    # but didn't specify the certificate at all.
    # The purpose of the certificate is to authenticate on the server
    # context.load_default_certs(Purpose.SERVER_AUTH)
    # You don't have to specify the purpose to connect, but if you get a purpose error, you know where to find it
    ssl_context.load_default_certs()


def set_client_ssl_context_certificate_verification_ignore(ssl_context):
    # If we want to ignore bad server certificates when connecting as a client, we need to think about security.
    # If you care, you should not need to do it, for MITM possibilities.
    # To do this anyway we need first to disable 'check_hostname' and only
    # then set 'verify_mode' to 'ssl.CERT_NONE'. If we do it in backwards order, when 'verify_mode' comes before
    # 'check_hostname' then we'll get an exception that 'check_hostname' needs to be False.
    # This setting should eliminate ssl error on 'SSLSocket.connect()':
    # ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED]
    # certificate verify failed: unable to get local issuer certificate (_ssl.c:997)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE


def load_certificate_and_key_into_server_ssl_context(
        ssl_context,
        certificate_file_path: str,
        key_file_path: str = None,
        print_kwargs: dict = None
):
    """

    :param ssl_context:
    :param certificate_file_path:
    :param key_file_path: string, full file path for the key file. If the certificate contains both the key and the
        certificate in one file, "keyfile" parameter can be None. Default is None.
    :param print_kwargs: dictionary, keyword arguments for 'print_api' function.
    :return:
    """

    # If the certificate contains both the key and the certificate in one file,
    # "keyfile" parameter can be "None".
    try:
        ssl_context.load_cert_chain(certfile=certificate_file_path, keyfile=key_file_path)
    except ssl.SSLError as exception_object:
        if 'PEM' in str(exception_object):
            message = \
                f'Custom Certificate Problem with either certificate or key.\n' \
                f'Make sure that both are in ".PEM" format\n' \
                f"Or your certificate contains the key if you didn't specify it.\n" \
                f'{exception_object}'
            print_api(message, error_type=True, logger_method="critical", **print_kwargs)


def create_server_ssl_context___load_certificate_and_key(certificate_file_path: str, key_file_path):
    # Create and set ssl context for server.
    ssl_context = create_ssl_context_for_server()
    # Load certificate into context.
    load_certificate_and_key_into_server_ssl_context(ssl_context, certificate_file_path, key_file_path)
    # Return ssl context only.
    return ssl_context


@exception_wrapper.connection_exception_decorator
def wrap_socket_with_ssl_context_server(socket_object, ssl_context, dns_domain: str = None, print_kwargs: dict = None):
    """
    This function is wrapped with exception wrapper.
    After you execute the function, you can get the error message if there was any with:
        error_message = wrap_socket_with_ssl_context_server.message

    :param socket_object:
    :param ssl_context:
    :param dns_domain:
    :param print_kwargs:
    :return:
    """

    # Wrapping the server socket with SSL context. This should happen right after setting up the raw socket.
    # ssl_socket = ssl_context.wrap_socket(socket_object, server_side=True, do_handshake_on_connect=False)
    # ssl_socket.do_handshake()
    ssl_socket = ssl_context.wrap_socket(socket_object, server_side=True)
    return ssl_socket


def wrap_socket_with_ssl_context_server_with_error_message(
        socket_object, ssl_context, dns_domain: str = None, print_kwargs: dict = None):

    ssl_socket = wrap_socket_with_ssl_context_server(
        socket_object, ssl_context, dns_domain=dns_domain, print_kwargs=print_kwargs)
    error_message = wrap_socket_with_ssl_context_server.message

    return ssl_socket, error_message


def wrap_socket_with_ssl_context_client(socket_object, ssl_context, server_hostname: str = None):
    # Wrapping the socket with "ssl.SSLContext" object to make "ssl.SSLSocket" object.
    # With "server_hostname" you don't have to use DNS hostname, you can use the IP, just remember to add
    # the address to your Certificate under "X509v3 Subject Alternative Name"
    # SSL wrapping should happen after socket creation and before connection:
    # https://docs.python.org/3/library/ssl.html
    return ssl_context.wrap_socket(sock=socket_object, server_side=False, server_hostname=server_hostname)


def bind_socket_with_ip_port(socket_object, ip_address: str, port: int, **kwargs):
    # "bind()" the socket object to the server host address and the listening port.
    # IPv4 address and port are required for the "AF_INET" socket family (can be IPv4, hostname, empty). On empty
    # string, the server will accept connections on all available IPv4 interfaces.
    # You need to bind only the main listening socket, no need to throw it to threads
    # Bind will be only set for a server and not for the client. Bind assigns the port to the application that uses
    # it, since it is always needs to be listening for new connections, unlike client that only sends the request
    # and doesn't listen to the specific port.
    try:
        socket_object.bind((ip_address, port))
    # WindowsError is inherited from OSError. It is available when OSError has "WinError" line in it.
    # Off course under linux it will be different.
    except WindowsError as exception_object:
        # Check if the specific "WinError" is "10049"
        # Also, "sys.exc_info()[1].winerror" can be used, but less specific to WindowsError in this case
        # if sys.exc_info()[1].winerror == 10049:
        if exception_object.winerror == 10049:
            message = f"Couldn't bind to interface [{ip_address}] on port [{port}]. Check the address of the interface."
            print_api(message, error_type=True, logger_method="critical", **kwargs)
        # If it's not the specific WinError, then raise the exception regularly anyway.
        else:
            raise


def set_listen_on_socket(socket_object, **kwargs):
    # You need to listen to the main socket once.
    # The number given within 'listen()' is the size of the backlog queue - number of pending requests.
    # Leaving empty will choose default.
    # Specifying number higher than the OS is supporting will truncate to that number. Some linux distributions
    # support maximum of 128 'backlog' sockets. Specifying number higher than 128 will truncate to 128 any way.
    # To determine the maximum listening sockets, you may use the 'socket' library and 'SOMAXCONN' parameter
    # from it.
    socket_object.listen(socket.SOMAXCONN)
    ip_address, port = base.get_destination_address_from_socket(socket_object)

    print_api(f"Listening for new connections on: {ip_address}:{port}", **kwargs)


# ======================================================================================
# Socket Creator Presets

def wrap_socket_with_ssl_context_client___default_certs___ignore_verification(
        socket_object, server_hostname: str = None):
    ssl_context: ssl.SSLContext = create_ssl_context_for_client()
    set_client_ssl_context_default_certs(ssl_context)
    set_client_ssl_context_certificate_verification_ignore(ssl_context)
    ssl_socket: ssl.SSLSocket = wrap_socket_with_ssl_context_client(
        socket_object, ssl_context, server_hostname=server_hostname)

    return ssl_socket


def wrap_socket_with_ssl_context_server_sni_extended(
        socket_object, config: dict, dns_domain: str = None, print_kwargs: dict = None):

    ssl_context = create_ssl_context_for_server()

    sni.add_sni_callback_function_reference_to_ssl_context(
        ssl_context=ssl_context, config=config, dns_domain=dns_domain, use_default_sni_function=True,
        use_sni_extended=True, print_kwargs=print_kwargs)

    server_certificate_file_path, server_private_key_file_path = \
        certificator.select_server_ssl_context_certificate(config=config, print_kwargs=print_kwargs)

    # If the user chose 'sni_create_server_certificate_for_each_domain = 1' in the configuration file,
    # it means that 'self.server_certificate_file_path' will be empty, which is OK, since we'll inject
    # dynamically created certificate from certs folder through SNI.
    if server_certificate_file_path:
        load_certificate_and_key_into_server_ssl_context(
            ssl_context, server_certificate_file_path, server_private_key_file_path,
            print_kwargs=print_kwargs)

    ssl_socket, error_message = wrap_socket_with_ssl_context_server_with_error_message(
        socket_object, ssl_context, dns_domain=dns_domain, print_kwargs=print_kwargs)
    return ssl_socket, error_message

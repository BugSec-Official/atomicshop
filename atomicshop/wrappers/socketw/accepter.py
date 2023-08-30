from . import exception_wrapper


@exception_wrapper.connection_exception_decorator
def accept_connection(socket_object, dns_domain, print_kwargs: dict = None):
    """
    Accept connection from client.
    This function is wrapped with exception wrapper.
    After you execute the function, you can get the error message if there was any with:
        error_message = accept_connection.message

    :param socket_object:
    :param dns_domain:
    :param print_kwargs:
    :return:
    """

    client_socket = None
    client_address_tuple: tuple = tuple()
    message = str()

    # "accept()" bloc script I/O calls until receives network connection. When client connects "accept()"
    # returns client socket and client address. Non-blocking mode is supported with "setblocking()", but you
    # need to change your application accordingly to handle this.
    # The client socket will contain the address and the port.
    # Since the client socket is thrown each time to a thread function, it can be overwritten in the main loop
    # and thrown to the function again. Accept creates new socket each time it is being called on the main
    # socket.
    # "accept()" method of the "ssl.SSLSocket" object returns another "ssl.SSLSocket" object and not the
    # regular socket
    client_socket, client_address_tuple = socket_object.accept()

    return client_socket, client_address_tuple


def accept_connection_with_error(socket_object, dns_domain, print_kwargs: dict = None):
    client_socket, client_address_tuple = accept_connection(socket_object, dns_domain, print_kwargs=print_kwargs)
    error_message = accept_connection.message

    return client_socket, client_address_tuple, error_message

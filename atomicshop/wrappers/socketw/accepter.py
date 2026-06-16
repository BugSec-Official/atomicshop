from ...print_api import print_api


def accept_connection(
        socket_object,
        domain_from_dns_server: str | None = None,
        print_kwargs: dict | None = None
):
    # noinspection GrazieInspection
    """
        Block on accept() and return (client_socket, client_address, error_message).

        error_message is None on success. On a dropped/failed accept the socket and
        address are None and error_message holds a one-line reason. accept() never
        raises out of this function, so one bad client can't kill the accept loop.

        :param socket_object: listening socket to accept on.
        :param domain_from_dns_server: domain to show in the error line; falls back
            to the listening IP when not provided.
        :param print_kwargs: keyword arguments forwarded to 'print_api'.
        """
    print_kwargs = print_kwargs or {}
    listen_ipv4, port = socket_object.getsockname()
    # If 'domain_from_dns_server' is provided, use it first.
    host = domain_from_dns_server or listen_ipv4

    try:
        # accept() blocks until a client connects, then returns a fresh per-client
        # socket and its (ip, port). On a ssl.SSLSocket it returns another SSLSocket.
        client_socket, client_address = socket_object.accept()
        return client_socket, client_address, None
    except ConnectionAbortedError:
        error_message = f"Socket Accept: {host}:{port}: connection aborted by host software."
    except ConnectionResetError:
        error_message = f"Socket Accept: {host}:{port}: connection reset by remote host."
    except Exception as e:
        error_message = f"Socket Accept: {host}:{port}: {e}"

    print_api(error_message, logger_method='error', traceback_string=True, oneline=True, **print_kwargs)
    return None, None, error_message

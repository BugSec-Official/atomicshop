import socket
import time


LOCALHOST_IPV4: str = '127.0.0.1'
DEFAULT_IPV4: str = socket.gethostbyname(socket.gethostname())
THIS_DEVICE_IP_LIST: list = [LOCALHOST_IPV4, DEFAULT_IPV4]


def get_local_network_interfaces_ip_address(family_type: str = None, ip_only: bool = False) -> list:
    """
    Return list of IP addresses of local network interfaces.

    :param family_type: string, available options:
        None: default, returns both ipv4 and ipv6 addresses.
        "ipv4": returns only ipv4 addresses.
        "ipv6": returns only ipv6 addresses.
    :param ip_only: bool, if True, returns only IP addresses, if False, returns tuples with all objects.
    :return: list.
    """
    family: int = 0
    if not family_type:
        family = 0
    elif family_type == "ipv4":
        family = socket.AF_INET
    elif family_type == "ipv6":
        family = socket.AF_INET6

    network_interfaces_tuples = list(socket.getaddrinfo(socket.gethostname(), None, family=family))

    if not ip_only:
        return network_interfaces_tuples
    else:
        return [i[4][0] for i in network_interfaces_tuples]


def get_destination_address_from_socket(socket_object):
    """
    Return destination IP and port.

    :param socket_object:
    :return:
    """
    # return ip_address, port
    return socket_object.getsockname()[0], socket_object.getsockname()[1]


def get_source_address_from_socket(socket_object):
    """
    Return source IP and port.

    :param socket_object:
    :return:
    """
    # return ip_address, port
    return socket_object.getpeername()[0], socket_object.getpeername()[1]


def get_source_destination(socket_object):
    return get_source_address_from_socket(socket_object), get_destination_address_from_socket(socket_object)


def set_socket_timeout(socket_object, seconds: int = 1):
    # Setting timeout on the socket before "accept()" drastically slows down connections.
    socket_object.settimeout(seconds)


def get_default_ip_address() -> str:
    """
    Get the default IP address of the system (in other words the interface IPv4 that is used for internet connection).
    :return: string.
    """
    return socket.gethostbyname(socket.gethostname())


def is_socket_closed(socket_object) -> bool:
    """
    Check if the socket is closed.
    :param socket_object: socket object or ssl socket object.
    :return: bool.
    """
    try:
        # If the socket is closed, the fileno() method will raise an exception or return -1.

        if socket_object.fileno() == -1:
            return True
        else:
            return False
    except socket.error:
        return False


def get_host_name_from_ip_address_with_timeout(ip_address: str, timeout: float = 0.01) -> str:
    """
    Get the host name from the IP address with a timeout.
    Uses concurrent.futures.ThreadPoolExecutor to enforce the timeout,
    since socket.gethostbyaddr has no native timeout parameter.
    Returns empty string if lookup times out or fails.

    :param ip_address: string, IP address.
    :param timeout: float, timeout in seconds. 10ms is more than enough to get the host name from ip address on local network.
        The problem is that 'socket.gethostbyaddr' doesn't have a built-in timeout, so it takes about 5 seconds
        to finish the process if the host name can't be found. On regular occasion it will take 1-10 ms to
        finish this action. So, we're taking the maximum.
    :return: string, host name or empty string.
    """
    from concurrent.futures import ThreadPoolExecutor, TimeoutError

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(socket.gethostbyaddr, ip_address)
    try:
        result = future.result(timeout=timeout)
        return result[0]
    except (TimeoutError, socket.herror):
        return ""
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def get_host_name_from_ip_address(ip_address: str) -> str:
    """
    Get the host name from the IP address.
    :param ip_address: string, IP address.
    :return: string, host name.
    """

    return get_host_name_from_ip_address_with_timeout(ip_address)


def wait_for_ip_bindable(
    ip: str,
    port: int = 0,
    timeout: float = 15.0,
    interval: float = 0.5,
) -> None:
    """
    Wait until a single IP is bindable (or timeout).

    Raises TimeoutError if the IP cannot be bound within 'timeout' seconds.
    """
    deadline = time.time() + timeout
    # last_err: OSError | None = None

    while True:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind((ip, port))
            return  # success
        except OSError as e:
            last_err = e
        finally:
            s.close()

        # If we've reached/exceeded the deadline, stop (this still allows one attempt when timeout==0).
        if time.time() >= deadline:
            raise TimeoutError(
                f"IP {ip} not bindable within {timeout} seconds; "
                f"last error: {last_err}"
            )

        time.sleep(interval)
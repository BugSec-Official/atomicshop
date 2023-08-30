import socket
import select

from . import receiver


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


def get_protocol_type(client_socket) -> str:
    """
    Return protocol type of the incoming socket after 'accept()'.
    :param client_socket: incoming socket after 'accept()'.
    :return: socket type, string.
    """

    ready_to_read, _, _ = select.select([client_socket], [], [], 0)

    if ready_to_read:
        first_byte = receiver.peek_first_byte(client_socket)

        if first_byte and first_byte[0] == 0x16:
            return 'tls'
        else:
            return 'non-tls'
    else:
        return None

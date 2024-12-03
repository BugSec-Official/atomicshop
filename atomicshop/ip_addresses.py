import ipaddress
from typing import Union, Literal


def is_ip_address(
        string_value: str,
        ip_type: Union[
            Literal['ipv4', 'ipv6'],
            None] = None
) -> bool:
    """
    The function checks if the string is an IPv4 or IPv6 address.

    :param string_value: string to check.
    :param ip_type: string, 'ipv4' or 'ipv6'. If None, then both IPv4 and IPv6 addresses are checked.
    :return: boolean.
    """

    try:
        if not ip_type:
            ipaddress.ip_address(string_value)
        elif ip_type == 'ipv4':
            ipaddress.IPv4Address(string_value)
        elif ip_type == 'ipv6':
            ipaddress.IPv6Address(string_value)
    except (ipaddress.AddressValueError, ValueError):
        return False

    return True


def get_ip_type(ip_address: str) -> Union[Literal['ipv4', 'ipv6'], None]:
    """
    The function checks if the string is an IPv4 or IPv6 address.

    :param ip_address: string to check.
    :return: string, 'ipv4' or 'ipv6'.
    """

    if is_ip_address(ip_address, ip_type='ipv4'):
        return 'ipv4'
    elif is_ip_address(ip_address, ip_type='ipv6'):
        return 'ipv6'
    else:
        return None

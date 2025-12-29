import sys
import socket
from typing import Union
import ipaddress
import subprocess

import psutil


def is_ip_address(string_value: str) -> bool:
    try:
        ipaddress.IPv4Address(string_value)
        return True
    except (ipaddress.AddressValueError, ValueError):
        return False


def get_default_internet_ipv4(target: str = "8.8.8.8") -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect((target, 80))  # no packet sent; OS just chooses a route
        return s.getsockname()[0]  # local address of that route


def get_default_connection_name() -> Union[dict, None]:
    """
    Function to get the default network interface.
    :return: dict[interface_name: details] or None.
    """
    # Get all interfaces.
    interfaces: dict = psutil.net_if_addrs()
    default_ip_address: str = get_default_internet_ipv4()

    for interface, details in interfaces.items():
        for address in details:
            # Check if the address is an IPv4 address (AF_INET) and not a loopback (127.0.0.1)
            if address.family == socket.AF_INET and not address.address.startswith('127.'):
                # Check if the address is the default IP address.
                if address.address == default_ip_address:
                    return {interface: details}

    return None


def get_default_interface_name() -> str:
    default_connection_name_dict: dict = get_default_connection_name()
    if not default_connection_name_dict:
        return ""
    # Get the first key from the dictionary.
    connection_name: str = list(default_connection_name_dict.keys())[0]
    return connection_name


def set_default_gateway_ipv4(gateway_ipv4: str) -> str | None:
    interface_name: str = get_default_interface_name()
    if not interface_name:
        return "Could not determine the default network interface name."

    # Set the default gateway using 'netsh' command.
    command: str = f'netsh interface ipv4 set dns name="{interface_name}" static {gateway_ipv4} primary'
    result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout: str = result.stdout.decode().strip()
    stderr: str = result.stderr.decode().strip()

    if result.returncode != 0:
        return (f"stdout: {stdout}\n"
                f"stderr: {stderr}")

    return None


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: set_default_dns_gateway.py <IPv4>", file=sys.stderr)
        return 1

    dns_ipv4: str = sys.argv[1]
    if not is_ip_address(dns_ipv4):
        print("Invalid IPv4 address", file=sys.stderr)
        return 1

    error_message: str | None = set_default_gateway_ipv4(dns_ipv4)
    if error_message:
        print(f"Failed to set default DNS gateway:\n{error_message}", file=sys.stderr)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
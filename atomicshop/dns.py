import socket
import argparse

# noinspection PyPackageRequirements
import dns.resolver

from . import print_api
from . import networks
from .permissions import permissions
from .wrappers.pywin32w.wmis import win32networkadapter
from .wrappers import netshw


# Defining Dictionary of Numeric to String DNS Query Types.
# https://en.wikipedia.org/wiki/List_of_DNS_record_types
TYPES_DICT = {
    '1': 'A',
    '2': 'NS',
    '5': 'CNAME',
    '6': 'SOA',
    '12': 'PTR',
    '15': 'MX',
    '28': 'AAAA',
    '33': 'SRV',
    '65': 'HTTPS',
    '255': 'ANY'
}


def resolve_dns_localhost(domain_name: str, dns_servers_list: list = None, print_kwargs: dict = None) -> str:
    """
    Resolve DNS queries when the DNS gateway is localhost.

    :param domain_name: string of Domain name to resolve.
    :param dns_servers_list: List of DNS services (IPv4 strings) to resolve.
    :param print_kwargs: dict, that contains all the arguments for 'print_api' function.

    :return: the first result of the DNS query.
    """

    if not print_kwargs:
        print_kwargs = dict()

    # If 'dns_servers_list' is empty, assign Google DNS server by default.
    if not dns_servers_list:
        dns_servers_list = ['8.8.8.8']

    # noinspection PyTypeChecker
    connection_ip: str = None

    try:
        # The class should be called separately for each thread. You can't create it in the main thread and
        # pass it to threads as object.
        # Building DNS Resolver, it will receive DNS servers from configuration file to contact
        resolver = dns.resolver.Resolver()
        # Assigning the dns service address we acquired from configuration file to resolver
        resolver.nameservers = dns_servers_list
        # Get the DNS
        function_server_address = resolver.resolve(domain_name, 'A')
        # Get only the first entry of the list of IPs [0]
        connection_ip = function_server_address[0].to_text()
        message = f"Resolved to [{connection_ip}]"
        print_api.print_api(message, **print_kwargs)
    except dns.resolver.NXDOMAIN:
        message = f"Domain {domain_name} doesn't exist - Couldn't resolve with {dns_servers_list}."
        print_api.print_api(message, **print_kwargs, error_type=True, logger_method='error')
        pass

    return connection_ip


def get_default_dns_gateway() -> tuple[bool, list[str]]:
    """
    Get the default DNS gateway from the system.
    :return: tuple(is dynamic boolean, list of DNS server IPv4s).
    """

    interfaces_with_dns_settings: list[dict] = netshw.get_netsh_ipv4()

    default_interface_ipv4 = socket.gethostbyname(socket.gethostname())
    is_dynamic, dns_servers = None, None
    for interface in interfaces_with_dns_settings:
        if default_interface_ipv4 in interface['ip_addresses']:
            is_dynamic = interface['dns_mode']
            dns_servers = interface['dns_servers']
            break

    return is_dynamic, dns_servers


def get_default_dns_gateway_with_dns_resolver() -> list[str]:
    """
    Get the default DNS gateway from the system using dns.resolver.
    :return: tuple(is dynamic boolean, list of DNS server IPv4s).
    """

    resolver = dns.resolver.Resolver()
    dns_servers = list(resolver.nameservers)
    return dns_servers


def set_interface_dns_gateway_static(
        interface_name: str,
        dns_servers: list[str]
) -> None:
    """
    Set the DNS servers for a network adapter.
    :param interface_name: string, adapter name as shown in the network settings.
    :param dns_servers: list of strings, DNS server IPv4 addresses.
    :return: None
    """

    win32networkadapter.set_dns_server(interface_name=interface_name, dns_servers=dns_servers)


def set_interface_dns_gateway_dynamic(
        interface_name: str = None
) -> None:
    """
    Set the DNS servers for a network adapter to obtain them automatically from DHCP.
    :param interface_name: string, adapter name as shown in the network settings.
    :return: None
    """

    win32networkadapter.set_dns_server(
        interface_name=interface_name, dns_servers=None)


def default_dns_gateway_main() -> int:
    """
    Main function for the default DNS gateway manipulations.
    :return: None
    """

    argparse_obj = argparse.ArgumentParser(description="Get/Set the DNS gateway for the network adapter.")
    arg_action_group = argparse_obj.add_mutually_exclusive_group(required=True)
    arg_action_group.add_argument(
        '-g', '--get', action='store_true', help='Get the default DNS gateway for the system.')
    arg_action_group.add_argument(
        '-s', '--set', type=str, nargs='+',
        help='Set static DNS gateway for the system, provide values with spaces between each value.\n'
             '   Example: -s 8.8.8.8 1.1.1.1.')
    arg_action_group.add_argument(
        '-d', '--dynamic', action='store_true',
        help='Set the DNS gateway to obtain automatically from DHCP.')

    arg_interface_group = argparse_obj.add_mutually_exclusive_group()
    arg_interface_group.add_argument(
        '-in', '--interface_name', type=str, help='Network Interface name as shown in the network settings.')
    arg_interface_group.add_argument(
        '-id', '--interface_default', action='store_true', help='Use the default network interface.')

    args = argparse_obj.parse_args()

    if (args.set or args.dynamic) and not (args.interface_name or args.interface_default):
        print_api.print_api(
            "Please provide the interface name [-in] or use the default interface [-id].", color='red')
        return 1

    if args.set or args.dynamic:
        if not permissions.is_admin():
            print_api.print_api("You need to run this script as an administrator", color='red')
            return 1

    def get_interface_name() -> str:
        if args.interface_default:
            return networks.get_default_interface_name()
        else:
            return args.interface_name

    if args.get:
        is_dynamic, dns_servers = get_default_dns_gateway()

        if is_dynamic:
            is_dynamic_string = 'Dynamic'
        else:
            is_dynamic_string = 'Static'
        print_api.print_api(f'DNS Gateway: {is_dynamic_string} - {dns_servers}', color='blue')
    elif args.set:
        # dns_servers_list: list = args.dns_servers.split(',')
        set_interface_dns_gateway_static(
            dns_servers=args.set, interface_name=get_interface_name())
    elif args.dynamic:
        set_interface_dns_gateway_dynamic(interface_name=get_interface_name())

    return 0
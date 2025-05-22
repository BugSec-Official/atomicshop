import argparse

# noinspection PyPackageRequirements
import dns.resolver

from . import print_api
from .permissions import permissions
from .wrappers.pywin32w.wmis import win32networkadapter
from .wrappers.winregw import winreg_network


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

    is_dynamic, dns_servers = winreg_network.get_default_dns_gateway()
    return is_dynamic, dns_servers


def get_default_dns_gateway_with_dns_resolver() -> list[str]:
    """
    Get the default DNS gateway from the system using dns.resolver.
    :return: tuple(is dynamic boolean, list of DNS server IPv4s).
    """

    resolver = dns.resolver.Resolver()
    dns_servers = list(resolver.nameservers)
    return dns_servers


def set_connection_dns_gateway_static(
        dns_servers: list[str],
        connection_name: str = None,
        use_default_connection: bool = False
) -> None:
    """
    Set the DNS servers for a network adapter.
    :param connection_name: string, adapter name as shown in the network settings.
    :param dns_servers: list of strings, DNS server IPv4 addresses.
    :param use_default_connection: bool, if True, the default network interface will be used. This is the connection
        that you internet is being used from.
    :return: None
    """

    win32networkadapter.set_dns_server(
        connection_name=connection_name, dns_servers=dns_servers, use_default_interface=use_default_connection)


def set_connection_dns_gateway_dynamic(
        connection_name: str = None,
        use_default_connection: bool = False
) -> None:
    """
    Set the DNS servers for a network adapter to obtain them automatically from DHCP.
    :param connection_name: string, adapter name as shown in the network settings.
    :param use_default_connection: bool, if True, the default network interface will be used. This is the connection
        that you internet is being used from.
    :return: None
    """

    win32networkadapter.set_dns_server(
        connection_name=connection_name, dns_servers=None, use_default_interface=use_default_connection)


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

    arg_connection_group = argparse_obj.add_mutually_exclusive_group()
    arg_connection_group.add_argument(
        '-cn', '--connection_name', type=str, help='Connection name as shown in the network settings.')
    arg_connection_group.add_argument(
        '-cd', '--connection_default', action='store_true', help='Use the default connection.')

    args = argparse_obj.parse_args()

    if (args.set or args.dynamic) and not (args.connection_name or args.connection_default):
        print_api.print_api(
            "Please provide the connection name [-cn] or use the default connection [-cd].", color='red')
        return 1

    if args.set or args.dynamic:
        if not permissions.is_admin():
            print_api.print_api("You need to run this script as an administrator", color='red')
            return 1

    if args.get:
        is_dynamic, dns_servers = get_default_dns_gateway()

        if is_dynamic:
            is_dynamic_string = 'Dynamic'
        else:
            is_dynamic_string = 'Static'
        print_api.print_api(f'DNS Gateway: {is_dynamic_string} - {dns_servers}', color='blue')
    elif args.set:
        # dns_servers_list: list = args.dns_servers.split(',')
        set_connection_dns_gateway_static(
            dns_servers=args.set, connection_name=args.connection_name,
            use_default_connection=args.connection_default)
    elif args.dynamic:
        set_connection_dns_gateway_dynamic(
            connection_name=args.connection_name, use_default_connection=args.connection_default)

    return 0
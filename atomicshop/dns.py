import dns.resolver

from .print_api import print_api


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

# Event Tracing DNS info.
ETW_DNS_INFO = {
    'provider_name': 'Microsoft-Windows-DNS-Client',
    'provider_guid': '{1C95126E-7EEA-49A9-A3FE-A378B03DDB4D}',
    # Event ID 3008 got DNS Queries and DNS Answers. Meaning, that information in ETW will arrive after DNS Response
    # is received and not After DNS Query is sent.
    'event_id': 3008
}


def resolve_dns_localhost(domain_name: str, dns_servers_list: list = None, print_kwargs: dict = None) -> str:
    """
    Resolve DNS queries when the DNS gateway is localhost.

    :param domain_name: string of Domain name to resolve.
    :param dns_servers_list: List of DNS services (IPv4 strings) to resolve.
    :param print_kwargs: dict, that contains all the arguments for 'print_api' function.

    :return: the first result of the DNS query.
    """

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
        print_api(message, **print_kwargs)
    except dns.resolver.NXDOMAIN:
        message = f"Domain {domain_name} doesn't exist - Couldn't resolve with {dns_servers_list}."
        print_api(message, **print_kwargs, error_type=True, logger_method='error')
        pass

    return connection_ip

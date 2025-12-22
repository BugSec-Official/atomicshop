from logging import Logger
from typing import Union

from win32com.client import CDispatch

from . import wmi_helpers, win32_networkadapterconfiguration
from ...psutilw import psutil_networks
from ....print_api import print_api


def list_network_adapters(wmi_instance: CDispatch = None) -> list[CDispatch]:
    """
    List all network adapters on the system, from the Win32_NetworkAdapter class.

    :param wmi_instance: WMI instance. You can get it from:
        wmi_helpers.get_wmi_instance()
    :return: list of Win32_NetworkAdapter objects.
    """

    if not wmi_instance:
        wmi_instance, _ = wmi_helpers.get_wmi_instance()

    # Query all network adapters
    adapters: list[CDispatch] = list(wmi_instance.ExecQuery("SELECT * FROM Win32_NetworkAdapter"))

    # Print adapter descriptions
    # for adapter in adapters:
    #     print(f"Description: {adapter.Description}, IPEnabled: {adapter.IPEnabled}")
    return adapters


def get_network_adapter_by_device_name(
        device_name: str,
        wmi_instance: CDispatch = None
) -> Union[CDispatch, None]:
    """
    Get a network adapter by its name.

    :param device_name: string, adapter name as shown in the network settings.
    :param wmi_instance: WMI instance. You can get it from:
        wmi_helpers.get_wmi_instance()
    :return: Win32_NetworkAdapter object.
    """

    if not wmi_instance:
        wmi_instance, _ = wmi_helpers.get_wmi_instance()

    query: str = (
        "SELECT * FROM Win32_NetworkAdapter "
        f"WHERE Name LIKE '{device_name}'")
    adapters: list[CDispatch] = list(wmi_instance.ExecQuery(query))
    if not adapters:
        return None

    return adapters[0]


def get_default_network_adapter(wmi_instance: CDispatch = None):
    """
    Get the default network adapter.

    :param wmi_instance: WMI instance. You can get it from:
        wmi_helpers.get_wmi_instance()
    :return:
    """

    if not wmi_instance:
        wmi_instance, _ = wmi_helpers.get_wmi_instance()

    default_connection_name_dict: dict = psutil_networks.get_default_connection_name()
    # Get the first key from the dictionary.
    default_connection_name: str = list(default_connection_name_dict.keys())[0]
    adapters: list[CDispatch] = list_network_adapters(wmi_instance)

    for adapter in adapters:
        if default_connection_name == adapter.NetConnectionID:
            return adapter

    raise wmi_helpers.WMINetworkAdapterNotFoundError("Default network adapter not found.")


def set_dns_server(
        dns_servers: Union[list[str], None],
        interface_name: str = None,
        mac_address: str = None,
        verbose: bool = False,
        logger: Logger = None
):
    """
    Set the DNS servers for a network adapter.
    :param dns_servers: list of strings, DNS server IPv4 addresses.
        None, if you want to remove the DNS servers and make the interface to obtain them automatically from DHCP.
        list[str], if you want to set the DNS servers manually to the list of strings.
    :param interface_name: string, network interface name as shown in the network settings.
    :param mac_address: string, MAC address of the adapter. Format: '00:00:00:00:00:00'.

    :param verbose: bool, if True, print verbose output.
    :param logger: Logger object, if provided, will log the output instead of printing.
    :return:
    """

    adapter_config, current_adapter = win32_networkadapterconfiguration.get_adapter_network_configuration(
        interface_name=interface_name, mac_address=mac_address)

    if verbose:
        message = (
            f"Adapter [{current_adapter.Description}], Connection name [{current_adapter.NetConnectionID}]\n"
            f"Setting DNS servers to {dns_servers}")
        print_api(message, color='blue', logger=logger)

    # Set DNS servers
    wmi_helpers.call_method(adapter_config, 'SetDNSServerSearchOrder', dns_servers)

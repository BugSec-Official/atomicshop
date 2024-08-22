from typing import Union

import win32com.client

from . import helpers
from ...psutilw import networks
from ....print_api import print_api


class NetworkAdapterNotFoundError(Exception):
    pass


def list_network_adapters() -> list:
    # Initialize the WMI client
    wmi = win32com.client.Dispatch('WbemScripting.SWbemLocator')
    wmi_service = wmi.ConnectServer('.', 'root\\cimv2')

    # Query all network adapters
    adapters = wmi_service.ExecQuery("SELECT * FROM Win32_NetworkAdapter")

    # Print adapter descriptions
    # for adapter in adapters:
    #     print(f"Description: {adapter.Description}, IPEnabled: {adapter.IPEnabled}")
    return list(adapters)


def get_default_network_adapter():
    """
    Get the default network adapter.
    :return:
    """

    default_connection_name_dict: dict = networks.get_default_connection_name()
    # Get the first key from the dictionary.
    default_connection_name: str = list(default_connection_name_dict.keys())[0]
    adapters = list_network_adapters()

    for adapter in adapters:
        if default_connection_name == adapter.NetConnectionID:
            return adapter

    raise NetworkAdapterNotFoundError("Default network adapter not found.")


def get_wmi_network_configuration(
        use_default_interface: bool = False,
        connection_name: str = None,
        mac_address: str = None
) -> tuple:
    """
    Get the WMI network configuration for a network adapter.
    :param use_default_interface: bool, if True, the default network interface will be used.
        This is the adapter that your internet is being used from.
    :param connection_name: string, adapter name as shown in the network settings.
    :param mac_address: string, MAC address of the adapter. Format: '00:00:00:00:00:00'.
    :return: tuple(Win32_NetworkAdapterConfiguration, Win32_NetworkAdapter)
    """

    if use_default_interface and connection_name:
        raise ValueError("Only one of 'use_default_interface' or 'connection_name' must be provided.")
    elif not use_default_interface and not connection_name:
        raise ValueError("Either 'use_default_interface' or 'connection_name' must be provided.")

    adapters = list_network_adapters()

    current_adapter = None
    if use_default_interface:
        default_connection_name_dict: dict = networks.get_default_connection_name()
        # Get the first key from the dictionary.
        connection_name: str = list(default_connection_name_dict.keys())[0]

    if connection_name is None and mac_address is None:
        raise ValueError("Either 'connection_name' or 'mac_address' must be provided.")
    elif connection_name and mac_address:
        raise ValueError("Only one of 'connection_name' or 'mac_address' must be provided.")

    if connection_name:
        for adapter in adapters:
            if connection_name == adapter.NetConnectionID:
                current_adapter = adapter
                break

        if not current_adapter:
            raise NetworkAdapterNotFoundError(f"Adapter with connection name '{connection_name}' not found.")
    elif mac_address:
        for adapter in adapters:
            if mac_address == adapter.MACAddress:
                current_adapter = adapter
                break

        if current_adapter is None:
            raise NetworkAdapterNotFoundError(f"Adapter with MAC address '{mac_address}' not found.")

    # Initialize the WMI client
    wmi = win32com.client.Dispatch('WbemScripting.SWbemLocator')
    wmi_service = wmi.ConnectServer('.', 'root\\cimv2')

    # Query the network adapter configurations
    query = f"SELECT * FROM Win32_NetworkAdapterConfiguration WHERE Index='{current_adapter.DeviceID}'"
    adapter_configs = wmi_service.ExecQuery(query)

    # Check if the adapter exists
    if len(adapter_configs) == 0:
        raise NetworkAdapterNotFoundError(f"Adapter with connection name '{connection_name}' not found.")

    return adapter_configs[0], current_adapter


def set_dns_server(
        dns_servers: Union[list[str], None],
        use_default_interface: bool = False,
        connection_name: str = None,
        mac_address: str = None
):
    """
    Set the DNS servers for a network adapter.
    :param dns_servers: list of strings, DNS server IPv4 addresses.
        None, if you want to remove the DNS servers and make the interface to obtain them automatically from DHCP.
        list[str], if you want to set the DNS servers manually to the list of strings.
    :param use_default_interface: bool, if True, the default network interface will be used.
        This is the adapter that your internet is being used from.
    :param connection_name: string, adapter name as shown in the network settings.
    :param mac_address: string, MAC address of the adapter. Format: '00:00:00:00:00:00'.
    :return:
    """

    adapter_config, current_adapter = get_wmi_network_configuration(
        use_default_interface=use_default_interface, connection_name=connection_name, mac_address=mac_address)

    print_api(f"Adapter [{current_adapter.Description}], Connection name [{current_adapter.NetConnectionID}]\n"
              f"Setting DNS servers to {dns_servers}", color='blue')

    # Set DNS servers
    helpers.call_method(adapter_config, 'SetDNSServerSearchOrder', dns_servers)

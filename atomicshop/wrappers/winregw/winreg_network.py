import winreg
import socket


def get_network_interfaces_settings(
        interface_guid: str = None
) -> dict:
    """
    Get network interface settings from the Windows registry.

    :param interface_guid: str, GUID of the network interface to retrieve settings for.
        If None, settings for all interfaces will be retrieved.
    :return: dict, network interface settings.
    """
    registry_path = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
    network_info = {}

    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path) as interfaces_key:
        interface_count = winreg.QueryInfoKey(interfaces_key)[0]

        for i in range(interface_count):
            current_interface_guid = winreg.EnumKey(interfaces_key, i)

            # If an interface GUID is provided, and it doesn't match the current one, skip it
            if interface_guid and interface_guid != current_interface_guid:
                continue

            interface_path = f"{registry_path}\\{current_interface_guid}"
            interface_data = {}

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, interface_path) as key:
                value_count = winreg.QueryInfoKey(key)[1]

                for j in range(value_count):
                    value_name, value_data, _ = winreg.EnumValue(key, j)
                    interface_data[value_name] = value_data

                # Populate the dictionary for the current interface
                network_info[current_interface_guid] = interface_data

    return network_info


def get_network_connections_to_guids() -> dict:
    """
    Get a dictionary mapping network connection names to their corresponding GUIDs.

    :return: dict, GUIDs to connection names.
    """
    adapters = {}
    registry_path = r"SYSTEM\CurrentControlSet\Control\Network\{4D36E972-E325-11CE-BFC1-08002BE10318}"

    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path) as network_key:
        adapter_count = winreg.QueryInfoKey(network_key)[0]

        for i in range(adapter_count):
            adapter_guid = winreg.EnumKey(network_key, i)
            adapter_path = f"{registry_path}\\{adapter_guid}\\Connection"

            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, adapter_path) as connection_key:
                    adapter_name, _ = winreg.QueryValueEx(connection_key, "Name")
                    adapters[adapter_guid] = adapter_name
            except FileNotFoundError:
                # Some GUIDs might not have a corresponding 'Connection' key, so we skip them
                continue

    return adapters


def get_enum_info_by_pnpinstanceid(
        pnp_instance_id: str
) -> dict:
    """
    Get all information from the Enum registry key for a device with a specific PnPInstanceId.

    :param pnp_instance_id: str, PnPInstanceId of the device.
    :return: dict, device information.
    """
    enum_registry_path = r"SYSTEM\CurrentControlSet\Enum"
    device_info = {}

    # Construct the full path to the device in the Enum registry
    hardware_path = f"{enum_registry_path}\\{pnp_instance_id}"

    # Open the registry key corresponding to the device
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, hardware_path) as hardware_key:
        num_values = winreg.QueryInfoKey(hardware_key)[1]

        # Retrieve all values under this key
        for i in range(num_values):
            value_name, value_data, _ = winreg.EnumValue(hardware_key, i)
            device_info[value_name] = value_data

    return device_info


def get_network_connections_details(get_enum_info: bool = True) -> dict:
    """
    Get network adapter details from the Windows registry.

    :param get_enum_info: bool, if True, retrieve all information from the corresponding Enum key.
        This is useful for getting additional information about the network adapter, like make, model, diver details.
    :return: dict, network adapter details.
    """
    adapter_details = {}
    network_registry_path = r"SYSTEM\CurrentControlSet\Control\Network\{4D36E972-E325-11CE-BFC1-08002BE10318}"

    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, network_registry_path) as network_key:
        adapter_count = winreg.QueryInfoKey(network_key)[0]

        for i in range(adapter_count):
            adapter_guid = winreg.EnumKey(network_key, i)
            adapter_path = f"{network_registry_path}\\{adapter_guid}\\Connection"

            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, adapter_path) as connection_key:
                    adapter_name, _ = winreg.QueryValueEx(connection_key, "Name")
                    pnp_instance_id, _ = winreg.QueryValueEx(connection_key, "PnPInstanceId")

                    # Get all information from the corresponding Enum key
                    if get_enum_info:
                        enum_info: dict = get_enum_info_by_pnpinstanceid(pnp_instance_id)
                    else:
                        enum_info: dict = {}

                    # Store the retrieved information
                    adapter_details[adapter_guid] = {
                        "Name": adapter_name,
                        "PnPInstanceId": pnp_instance_id,
                        "EnumInfo": enum_info
                    }

            except FileNotFoundError:
                continue

    return adapter_details


def get_default_dns_gateway() -> tuple[bool, list[str]]:
    """
    Get the default DNS gateway from the Windows registry.

    :return: tuple(is dynamic boolean, list of DNS server IPv4s).
    """

    # Get current default IPv4 address of the interface that is being used for internet.
    default_ipv4_address: str = socket.gethostbyname(socket.gethostname())

    # Get all network interface settings from the registry.
    all_interfaces_configurations = get_network_interfaces_settings()

    # Find the interface that has this IPv4 assigned.
    function_result: tuple = tuple()
    for interface_guid, interface_settings in all_interfaces_configurations.items():
        current_interface_static_ipv4_address: list = interface_settings.get('IPAddress', None)
        current_interface_dynamic_ipv4_address: str = interface_settings.get('DhcpIPAddress', None)

        static_and_ip_match: bool = (
                current_interface_static_ipv4_address and
                current_interface_static_ipv4_address[0] == default_ipv4_address)
        dynamic_and_ip_match: bool = (
                current_interface_dynamic_ipv4_address and
                current_interface_dynamic_ipv4_address == default_ipv4_address)
        if static_and_ip_match or dynamic_and_ip_match:
            if interface_settings['NameServer']:
                function_result = (False, interface_settings['NameServer'].split(','))
            else:
                function_result = (True, interface_settings['DhcpNameServer'].split(','))

            break

    # noinspection PyTypeChecker
    return function_result

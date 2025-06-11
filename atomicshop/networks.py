import socket
import time
from typing import Union
import os

from icmplib import ping
from icmplib.models import Host
from win32com.client import CDispatch

from .wrappers.pywin32w.wmis import win32networkadapter, win32_networkadapterconfiguration, wmi_helpers, msft_netipaddress
from .wrappers.ctyping import setup_device
from .wrappers.winregw import winreg_network


MICROSOFT_LOOPBACK_DEVICE_NAME: str = 'Microsoft KM-TEST Loopback Adapter'
MICROSOFT_LOOPBACK_DEVICE_INF_PATH    = os.path.join(os.environ["WINDIR"], "INF", "netloop.inf")
MICROSOFT_LOOPBACK_DEVICE_HARDWARE_ID = "*MSLOOP"
GUID_DEVCLASS_NET: str = '{4d36e972-e325-11ce-bfc1-08002be10318}'


def is_ip_alive(ip_address: str, timeout: int = 1) -> bool:
    """
    Returns True if icmplib.models.Host.is_alive returns True.
    """

    host_object: Host = ping(ip_address, count=1, timeout=timeout)

    return host_object.is_alive


def get_default_internet_ipv4() -> str:
    """
    Get the default IPv4 address of the interface that is being used for internet.
    :return: string, default IPv4 address.
    """

    return socket.gethostbyname(socket.gethostname())

def get_default_internet_ipv4_by_connect(target: str = "8.8.8.8") -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect((target, 80))  # no packet sent; OS just chooses a route
        return s.getsockname()[0]  # local address of that route


def get_default_internet_interface_name() -> str:
    """
    Get the default network interface name that is being used for internet.
    :return: string, default network interface name.
    """

    return socket.gethostname()


def get_microsoft_loopback_device_network_configuration(
        wmi_instance: CDispatch = None,
        timeout: int = 1,
) -> Union[
     tuple[CDispatch, str],
     tuple[None, None]
]:
    """
    Get the WMI Win32_NetworkAdapterConfiguration object of the Microsoft Loopback device.

    :param wmi_instance: WMI instance. You can get it from:
        wrappers.pywin32s.wmis.wmi_helpers.get_wmi_instance()
        If not specified the default WMI instance will be used '.'.
    :param timeout: int, timeout in seconds. Default is 1 second.
    :return: tuple(Win32_NetworkAdapterConfiguration, Win32_NetworkAdapter.PNPDeviceID)
        If the adapter is not found, it will return (None, None).
    """

    if not wmi_instance:
        wmi_instance, _ = wmi_helpers.get_wmi_instance()

    for _ in range(timeout):
        adapter: CDispatch = win32networkadapter.get_network_adapter_by_device_name(
            MICROSOFT_LOOPBACK_DEVICE_NAME, wmi_instance)
        if not adapter:
            # noinspection PyTypeChecker
            network_config = None
        else:
            network_config: CDispatch = win32_networkadapterconfiguration.get_network_configuration_by_adapter(
                adapter, wmi_instance=wmi_instance)

        if network_config:
            return network_config, adapter.PNPDeviceID
        time.sleep(1)

    return None, None


def create_microsoft_loopback_device():
    """
    Create a Microsoft Loopback device using the setupapi.dll.
    """
    setup_device.add_device(
        class_guid=GUID_DEVCLASS_NET,
        friendly_name=MICROSOFT_LOOPBACK_DEVICE_NAME,
        hardware_ids=MICROSOFT_LOOPBACK_DEVICE_HARDWARE_ID,
        inf_path=MICROSOFT_LOOPBACK_DEVICE_INF_PATH,
        force_install=True,
        quiet=True,
        existing_ok=True
    )


def get_create_microsoft_loopback_device_network_configuration(
        wmi_instance: CDispatch = None
) -> Union[
     tuple[CDispatch, str],
     tuple[None, None]
]:
    """
    Get the WMI Win32_NetworkAdapterConfiguration object of the Microsoft Loopback device.
    If it does not exist, create it.

    :param wmi_instance: WMI instance. You can get it from:
        wrappers.pywin32s.wmis.wmi_helpers.get_wmi_instance()
        If not specified the default WMI instance will be used '.'.
    :return: tuple(Win32_NetworkAdapterConfiguration, Win32_NetworkAdapter.PNPDeviceID)
        If the adapter is not found, it will return (None, None).
    """

    if not wmi_instance:
        wmi_instance, _ = wmi_helpers.get_wmi_instance()

    network_config, pnp_device_id = get_microsoft_loopback_device_network_configuration(wmi_instance=wmi_instance)

    if network_config:
        return network_config, pnp_device_id

    create_microsoft_loopback_device()

    network_config, pnp_device_id = get_microsoft_loopback_device_network_configuration(
        wmi_instance=wmi_instance, timeout=20)

    return network_config, pnp_device_id


def remove_microsoft_loopback_device(
        pnp_device_id: str
) -> bool:
    """
    Remove the Microsoft Loopback device using the setupapi.dll.

    :param pnp_device_id: string, PNPDeviceID of the device to remove.
    :return: bool, True if the device was removed successfully.
    """
    return setup_device.remove_device(
        pnp_device_id=pnp_device_id,
        class_guid=GUID_DEVCLASS_NET
    )


def change_interface_metric_restart_device(
        network_config: CDispatch,
        metric: int = 9999,
        wmi_instance: CDispatch = None
):
    """
    Change the interface metric and restart the device.
    You can check the metric in CMD with:
        route print

    :param network_config: CDispatch, Win32_NetworkAdapterConfiguration object.
    :param metric: int, new metric value.
    :param wmi_instance: WMI instance. You can get it from:
        wrappers.pywin32s.wmis.wmi_helpers.get_wmi_instance()
    """

    if not wmi_instance:
        wmi_instance, _ = wmi_helpers.get_wmi_instance()

    # 1) Registry tweak
    guid = network_config.SettingID
    winreg_network.change_metric_of_network_adapter(adapter_guid=guid, metric=metric)

    # 2) Bounce the NIC so TCP/IP re‑reads the new metric
    idx = network_config.Index
    adapter = wmi_instance.ExecQuery(f"SELECT * FROM Win32_NetworkAdapter WHERE Index={idx}")[0]

    adapter.ExecMethod_("Disable")
    time.sleep(1.0)
    adapter.ExecMethod_("Enable")


def get_wmi_network_adapter_configuration(
        use_default_interface: bool = False,
        connection_name: str = None,
        mac_address: str = None,
        wmi_instance: CDispatch = None,
        get_info_from_network_config: bool = True
) -> tuple:
    """
    Get the WMI network configuration for a network adapter.
    :param use_default_interface: bool, if True, the default network interface will be used.
        This is the adapter that your internet is being used from.
    :param connection_name: string, adapter name as shown in the network settings.
    :param mac_address: string, MAC address of the adapter. Format: '00:00:00:00:00:00'.
    :param wmi_instance: WMI instance. You can get it from:
        wrappers.pywin32s.wmis.wmi_helpers.get_wmi_instance()
        or default will be used.
    :param get_info_from_network_config: bool, if True, the function will return the network configuration info
        on the third position of the tuple. On False, it will return an empty dictionary.
    :return: tuple(Win32_NetworkAdapterConfiguration, Win32_NetworkAdapter, dict)
    """

    wmi_network_config, wmi_network_adapter = win32_networkadapterconfiguration.get_adapter_network_configuration(
        use_default_interface=use_default_interface,
        connection_name=connection_name,
        mac_address=mac_address,
        wmi_instance=wmi_instance
    )

    if get_info_from_network_config:
        adapter_info: dict = win32_networkadapterconfiguration.get_info_from_network_config(wmi_network_config)
    else:
        adapter_info: dict = {}

    return wmi_network_config, wmi_network_adapter, adapter_info


def generate_unused_ipv4_addresses_by_vlan(
        vlan: str,
        number_of_ips: int,
        skip_ips: list[str] = None
) -> list[str]:
    """
    Generate a list of unused IPv4 addresses in the given VLAN.

    :param vlan: string, VLAN in the format '192.168.0'.
    :param number_of_ips: int, number of IPs to generate.
    :param skip_ips: list of strings, IPs to skip.
    :return: list of strings, free IPv4 addresses.
    """

    generated_ips: list[str] = []
    counter: int = 1
    for i in range(number_of_ips):
        # Create the IP address.
        while True:
            ip_address = f"{vlan}.{counter}"
            counter += 1
            is_ip_in_use: bool = is_ip_alive(ip_address)
            if not is_ip_in_use and not ip_address in skip_ips:
                # print("[+] Found IP to assign: ", ip_address)
                generated_ips.append(ip_address)
                break
            else:
                # print(f"[!] IP {ip_address} is already in use or assigned to the adapter.")
                continue

    return generated_ips


def generate_unused_ipv4_addresses_from_ip(
        ip_address: str,
        mask: str,
        number_of_ips: int,
        skip_ips: list[str] = None
) -> tuple[list[str], list[str]]:
    """
    Generate a list of unused IPv4 addresses in the given VLAN.

    :param ip_address: string, IP address, example: '192.168.0.1'.
        This address will be a part of skip_ips list, even if an empty list is passed.
    :param mask: string, subnet mask, example: '255.255.255.0'.
    :param number_of_ips: int, number of IPs to generate.
    :param skip_ips: list of strings, IPs to skip.
    :return: list of strings, unused IPv4 addresses.
    """

    if not skip_ips:
        skip_ips = []

    # Remove duplicate IPs from the skip_ips list, loses order.
    skip_ips = list(set(skip_ips))

    # Add the IP address to the list of IPs to skip.
    if ip_address not in skip_ips:
        skip_ips = [ip_address] + skip_ips

    # Get the VLAN of the default IPv4 address.
    default_vlan: str = ip_address.rsplit(".", 1)[0]


    # Find IPs to assign.
    generated_ips: list[str] = generate_unused_ipv4_addresses_by_vlan(
        vlan=default_vlan, number_of_ips=number_of_ips, skip_ips=skip_ips)

    # Add subnet masks to the IPs to assign.
    masks_for_ips: list[str] = []
    for ip_address in generated_ips:
        print(f"[+] Found IP to assign: {ip_address}")
        masks_for_ips.append(mask)

    return generated_ips, masks_for_ips


def set_dynamic_ip_for_adapter(
        network_config: CDispatch,
        reset_dns: bool = True,
        reset_wins: bool = True
):
    """
    Set the IP address of the network adapter to dynamic from DHCP.
    :param network_config: CDispatch, Win32_NetworkAdapterConfiguration object.
    :param reset_dns: bool, if True, the DNS servers will be reset to automatic.
    :param reset_wins: bool, if True, the WINS servers will be reset to automatic.
    """

    win32_networkadapterconfiguration.set_dynamic_ip(
        nic_cfg=network_config, reset_dns=reset_dns, reset_wins=reset_wins)


def set_static_ip_for_adapter(
        network_config: CDispatch,
        ips: list[str],
        masks: list[str],
        gateways: list[str] = None,
        dns_gateways: list[str] = None,
        availability_wait_seconds: int = 0
):
    """
    Set the IP address of the network adapter to static.
    :param network_config: CDispatch, Win32_NetworkAdapterConfiguration object.
    :param ips: list of strings, IP addresses to assign.
    :param masks: list of strings, subnet masks to assign.
    :param gateways: list of strings, default gateways to assign.
    :param dns_gateways: list of strings, DNS servers to assign.
    :param availability_wait_seconds: int, seconds to wait for the adapter to be available after setting the IP address.
    """

    win32_networkadapterconfiguration.set_static_ips(
        network_config=network_config,
        ips=ips,
        masks=masks,
        gateways=gateways,
        dns_gateways=dns_gateways,
        availability_wait_seconds=availability_wait_seconds
    )


def add_virtual_ips_to_default_adapter_by_current_setting(
        number_of_ips: int = 0,
        virtual_ipv4s_to_add: list[str] = None,
        virtual_ipv4_masks_to_add: list[str] = None,
        set_virtual_ips_skip_as_source: bool = True,
        gateways: list[str] | None = None,
        dns_gateways: list[str] | None = None,
        availability_wait_seconds: int = 15,
        simulate_only: bool = False,
        locator: CDispatch = None,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """
    Add virtual IP addresses to the default network adapter.
    The adapter will set to static IP and DNS gateway, instead of dynamic DHCP.
    The first IPv4 address of the network_config will be used as VLAN and the unused IP addresses
    will be generated from it. Unused addresses decided by pinging them.
    Same for the subnet mask.

    While generating the IPs, the function will skip the already existing IPs in the adapter, like default gateway
    and DNS servers.

    :param number_of_ips: int, number of IPs to generate in addition to the IPv4s that already exist in the adapter.
        Or you add the IPs and masks to the adapter with the parameters virtual_ipv4s_to_add and virtual_ipv4_masks_to_add.

    :param virtual_ipv4s_to_add: list of strings, Add this IPv4 addresses to the current IPs of the adapter.
    :param virtual_ipv4_masks_to_add: list of strings, Add this subnet masks to the current subnet masks of the adapter.
        Or you generate the IPs and masks by specifying the number_of_ips parameter.

    :param set_virtual_ips_skip_as_source: bool, if True, the SkipAsSource flag will be set for the virtual IPs.
        This is needed to avoid the endless accept() loop.
    :param gateways: list of strings, default IPv4 gateways to assign.
        None: The already existing gateways in the adapter will be used.
        []: No gateways will be assigned.
    :param dns_gateways: list of strings, IPv4 DNS servers to assign.
        None: The already existing DNS servers in the adapter will be used.
        []: No DNS servers will be assigned.
    :param availability_wait_seconds: int, seconds to wait for the adapter to be available after setting the IP address.
    :param simulate_only: bool, if True, the function will only prepare the ip addresses and return them without changing anything.
    :param locator: CDispatch, WMI locator object. If not specified, it will be created.

    :return: tuple of lists, (current_ipv4s, current_ipv4_masks, ips_to_assign, masks_to_assign)
    """

    if virtual_ipv4s_to_add and not virtual_ipv4_masks_to_add:
        raise ValueError("If you specify virtual_ipv4s_to_add, you must also specify virtual_ipv4_masks_to_add.")
    if virtual_ipv4_masks_to_add and not virtual_ipv4s_to_add:
        raise ValueError("If you specify virtual_ipv4_masks_to_add, you must also specify virtual_ipv4s_to_add.")

    if virtual_ipv4s_to_add and len(virtual_ipv4s_to_add) != len(virtual_ipv4_masks_to_add):
        raise ValueError("If you specify virtual_ipv4s_to_add, the number of IPs must be equal to the number of masks.")

    if number_of_ips > 0 and (virtual_ipv4s_to_add or virtual_ipv4_masks_to_add):
        raise ValueError("If you specify number_of_ips, you cannot specify virtual_ipv4s_to_add or virtual_ipv4_masks_to_add.")

    # Connect to WMi.
    wmi_civ2_instance, locator = wmi_helpers.get_wmi_instance(locator=locator)

    # initial_default_ipv4: str = socket.gethostbyname(socket.gethostname())

    # Get the default network adapter configuration.
    default_network_adapter_config, default_network_adapter, default_adapter_info = get_wmi_network_adapter_configuration(
        use_default_interface=True, wmi_instance=wmi_civ2_instance, get_info_from_network_config=True)

    current_ipv4s: list[str] = default_adapter_info['ipv4s']
    current_ipv4_masks: list[str] = default_adapter_info['ipv4_subnet_masks']

    # print(f"Current IPs: {current_ipv4s}")
    # current_ips_count: int = len(current_ipv4s)

    if number_of_ips > 0:
        ips_to_assign, masks_to_assign = generate_unused_ipv4_addresses_from_ip(
            ip_address=current_ipv4s[0],
            mask=current_ipv4_masks[0],
            number_of_ips=number_of_ips,
            skip_ips=current_ipv4s + default_adapter_info['default_gateways'] + default_adapter_info['dns_gateways']
        )
    elif virtual_ipv4s_to_add and virtual_ipv4_masks_to_add:
        ips_to_assign = virtual_ipv4s_to_add
        masks_to_assign = virtual_ipv4_masks_to_add
    else:
        ips_to_assign = []
        masks_to_assign = []

    if not simulate_only:
        # Final list of IPs to assign.
        ips: list[str] = current_ipv4s + ips_to_assign
        masks: list[str] = current_ipv4_masks + masks_to_assign

        # ---------- IP assignment --------------------------------------------
        if ips != current_ipv4s:
            # print("[+] Setting static IPv4 addresses …")
            if gateways is None:
                gateways = default_adapter_info['default_gateways']

            if dns_gateways is None:
                dns_gateways = default_adapter_info['dns_gateways']

            # We will get the default IP address of the machine.
            default_ip_address: str = socket.gethostbyname(socket.gethostname())
            # So we can make it the first IP in the list, but first remove it from the list.
            _ = ips.pop(ips.index(default_ip_address))
            # At this point we will copy the list of IPs that we will set the SkipAsSource flag for.
            ips_for_skip_as_source = ips.copy()
            # Add it back to the beginning of the list.
            ips.insert(0, default_ip_address)

            win32_networkadapterconfiguration.set_static_ips(
                default_network_adapter_config, ips=ips, masks=masks,
                gateways=gateways, dns_gateways=dns_gateways,
                availability_wait_seconds=availability_wait_seconds)

            # If there were already virtual IPs assigned to the adapter and already were set SkipAsSource,
            # we need to set SkipAsSource for them once again as well as for the new IPs.
            if set_virtual_ips_skip_as_source:
                wmi_standard_cimv2_instance, _ = wmi_helpers.get_wmi_instance(
                    namespace='root\\StandardCimv2', wmi_instance=wmi_civ2_instance, locator=locator)
                msft_netipaddress.set_skip_as_source(ips_for_skip_as_source, enable=True, wmi_instance=wmi_standard_cimv2_instance)
        else:
            # print("[!] No new IPs to assign.")
            pass

    return current_ipv4s, current_ipv4_masks, ips_to_assign, masks_to_assign
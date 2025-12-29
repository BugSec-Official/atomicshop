import socket
import time
from typing import Union, Literal
import os
import psutil
import ctypes
from logging import Logger
import subprocess

from icmplib import ping
from icmplib.models import Host
from win32com.client import CDispatch

from .print_api import print_api
from .wrappers.pywin32w.wmis import win32networkadapter, win32_networkadapterconfiguration, wmi_helpers
from .wrappers.ctyping import setup_device
from .wrappers.winregw import winreg_network
from .wrappers.psutilw import psutil_networks
from .wrappers import powershell_networking, netshw
from .wrappers.socketw import socket_base


MICROSOFT_LOOPBACK_DEVICE_NAME: str = 'Microsoft KM-TEST Loopback Adapter'
MICROSOFT_LOOPBACK_DEVICE_INF_PATH    = os.path.join(os.environ["WINDIR"], "INF", "netloop.inf")
MICROSOFT_LOOPBACK_DEVICE_HARDWARE_ID = "*MSLOOP"
GUID_DEVCLASS_NET: str = '{4d36e972-e325-11ce-bfc1-08002be10318}'


def is_ip_in_use_ping(ip_address: str, timeout: int = 1) -> bool:
    """
    Returns True if the IP address is pingable, False otherwise.
    :param ip_address: string, IP address to check.
    :param timeout: int, timeout in seconds. Default is 1 second.
    :return: bool, True if the IP address is pingable, False otherwise.
    """

    host_object: Host = ping(ip_address, count=1, timeout=timeout)

    return host_object.is_alive


def is_ip_in_use_arp(
        ipv4: str,
        gateway_ip: str = None
) -> tuple[
        Union[str, None],
        Union[bool, None]
]:
    """
    Windows only.
    Check if an IPv4 address is in use on the local network using ARP.
    :param ipv4: string, IPv4 address to check.
    :param gateway_ip: string, IPv4 address of the default gateway.
        How it works: If you provide the gateway_ip, the function will get yje MAC of the gateway,
        then it will get the MAC of the target IP address. If the MACs are the same, it means that the target IP's
        ARP reply is an ARP proxy reply from the gateway.
    :return: tuple (mac_address: str | None, via_gateway: bool | None)
        If the IP address is in use, mac_address will be the MAC address of the device using the IP address,
        else None. If gateway_ip is provided, via_gateway will be True if the MAC address is the same as the gateway's MAC address,
        False if it's different, and None if gateway_ip is not provided.
    """

    iphlpapi = ctypes.windll.iphlpapi
    ws2_32 = ctypes.windll.ws2_32

    def _send_arp(ip: str) -> str | None:
        """Return MAC string like 'aa:bb:cc:dd:ee:ff' if IP is claimed on the LAN, else None."""
        # inet_addr returns DWORD in network byte order
        # noinspection PyUnresolvedReferences
        dest_ip = ws2_32.inet_addr(ip.encode('ascii'))
        if dest_ip == 0xFFFFFFFF:  # INVALID
            raise ValueError(f"Bad IPv4 address: {ip}")

        mac_buf = ctypes.c_uint64(0)  # storage for up to 8 bytes
        mac_len = ctypes.c_ulong(ctypes.sizeof(mac_buf))  # in/out len
        # SrcIP=0 lets Windows pick the right interface
        # noinspection PyUnresolvedReferences
        rc = iphlpapi.SendARP(dest_ip, 0, ctypes.byref(mac_buf), ctypes.byref(mac_len))
        if rc != 0:  # Non-zero means no ARP reply / not on-link / other error
            return None

        # Extract the first 6 bytes from little-endian integer
        mac_int = mac_buf.value
        mac_bytes = mac_int.to_bytes(8, 'little')[:6]
        return ':'.join(f'{b:02x}' for b in mac_bytes)

    mac = _send_arp(ipv4)
    if mac is None:
        return None, None
    via_gateway = None
    if gateway_ip:
        gw_mac = _send_arp(gateway_ip)
        via_gateway = (gw_mac is not None and gw_mac.lower() == mac.lower())
    return mac, via_gateway


def __get_default_internet_ipv4() -> str:
    """
    FOR REFERENCE ONLY, DO NOT USE.
    DOESN'T WORK UNDER ALL CIRCUMSTANCES, CAN'T PINPOINT THE REASON.

    Get the default IPv4 address of the interface that is being used for internet.
    :return: string, default IPv4 address.
    """

    return socket.gethostbyname(socket.gethostname())


def get_default_internet_ipv4(target: str = "8.8.8.8") -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect((target, 80))  # no packet sent; OS just chooses a route
        return s.getsockname()[0]  # local address of that route


def get_default_interface_name() -> str:
    default_connection_name_dict: dict = psutil_networks.get_default_connection_name()
    if not default_connection_name_dict:
        return ""
    # Get the first key from the dictionary.
    connection_name: str = list(default_connection_name_dict.keys())[0]
    return connection_name


def list_network_interfaces() -> list[str]:
    """
    List all network interfaces on the system.
    :return: list of strings, network interface names.
    """

    return psutil_networks.list_network_interfaces()


def get_hostname() -> str:
    """
    Get the default network interface name that is being used for internet.
    :return: string, default network interface name.
    """

    return socket.gethostname()


def get_interface_ips_psutil(
        interface_name: str = None,
        ipv4: bool = True,
        ipv6: bool = True,
        localhost: bool = True,
        default_interface: bool = False
):
    if not ipv4 and not ipv6:
        raise ValueError("At least one of ipv4 or ipv6 must be True.")
    if default_interface and interface_name:
        raise ValueError("You can't specify both default_interface and interface_name.")

    if default_interface:
        # Get the default interface name.
        interface_name = get_default_interface_name()

    physical_ip_types: list[str] = []
    if ipv4:
        physical_ip_types.append("AF_INET")  # IPv4
    if ipv6:
        physical_ip_types.append("AF_INET6")  # IPv6

    interfaces: dict = psutil.net_if_addrs()

    ips = []
    for name, addresses in interfaces.items():
        if interface_name and interface_name != name:
                continue

        for address in addresses:
            if address.family.name in physical_ip_types:
                if not localhost and (address.address.startswith("127.") or address.address.startswith("::1")):
                    # Skip localhost addresses if localhost is True.
                    continue

                ips.append(address.address)
    return ips


def get_host_ips_psutil(
        localhost: bool = True,
        ipv4: bool = True,
        ipv6: bool = True
) -> list[str]:
    """
    Yield (ifname, family, ip) for all UP interfaces that have bindable addresses.

    Args:
        localhost: include 127.0.0.0/8 and ::1 if True.
        ipv4: include IPv4 addresses if True.
        ipv6: include IPv6 addresses if True.
    """
    stats = psutil.net_if_stats()

    ip_list: list[str] = []
    for ifname, addrs in psutil.net_if_addrs().items():
        st = stats.get(ifname)
        if not st or not st.isup:
            continue  # interface is down or unknown

        for a in addrs:
            fam = a.family
            if fam not in (socket.AF_INET, socket.AF_INET6):
                continue

            # Family filters
            if fam == socket.AF_INET and not ipv4:
                continue
            if fam == socket.AF_INET6 and not ipv6:
                continue

            ip = a.address

            # Skip placeholders/wildcards
            if fam == socket.AF_INET and ip == "0.0.0.0":
                continue
            if fam == socket.AF_INET6 and ip in ("::",):
                continue

            # Optionally skip loopback
            if not localhost:
                if fam == socket.AF_INET and ip.startswith("127."):
                    continue
                if fam == socket.AF_INET6 and (ip == "::1" or ip.startswith("::1%")):
                    continue

            # yield ifname, fam, ip
            ip_list.append(ip)

    return ip_list


def get_interface_ips_powershell(
        interface_name: str = None,
        ip_type: Literal["virtual", "dynamic", "all"] = "virtual"
) -> list[str]:
    """
    Get the IP addresses of a network interface using PowerShell.

    :param interface_name: string, name of the network interface.
        If None, all interfaces will be queried.
    :param ip_type: string, type of IP addresses to retrieve.
    :return: list of strings, IP addresses of the network interface.
    """

    return powershell_networking.get_interface_ips(interface_name=interface_name, ip_type=ip_type)


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
        interface_name: str = None,
        mac_address: str = None,
        wmi_instance: CDispatch = None,
        get_info_from_network_config: bool = True
) -> tuple:
    """
    Get the WMI network configuration for a network adapter.
    :param interface_name: string, adapter name as shown in the network settings.
    :param mac_address: string, MAC address of the adapter. Format: '00:00:00:00:00:00'.
    :param wmi_instance: WMI instance. You can get it from:
        wrappers.pywin32s.wmis.wmi_helpers.get_wmi_instance()
        or default will be used.
    :param get_info_from_network_config: bool, if True, the function will return the network configuration info
        on the third position of the tuple. On False, it will return an empty dictionary.
    :return: tuple(Win32_NetworkAdapterConfiguration, Win32_NetworkAdapter, dict)
    """

    wmi_network_config, wmi_network_adapter = win32_networkadapterconfiguration.get_adapter_network_configuration(
        interface_name=interface_name,
        mac_address=mac_address,
        wmi_instance=wmi_instance
    )

    if get_info_from_network_config:
        adapter_info: dict = win32_networkadapterconfiguration.get_info_from_network_config(wmi_network_config)
        adapter_info['name'] = wmi_network_adapter.NetConnectionID
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
            ip_address: str = f"{vlan}.{counter}"
            counter += 1
            is_ip_in_use, _ = is_ip_in_use_arp(ip_address)
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


def set_dynamic_ip_for_adapter_wmi(
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


def set_static_ip_for_adapter_wmi(
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


def add_virtual_ips_to_network_interface(
        interface_name: str,
        number_of_ips: int = 0,
        virtual_ipv4s_to_add: list[str] = None,
        virtual_ipv4_masks_to_add: list[str] = None,
        set_virtual_ips_skip_as_source: bool = True,
        simulate_only: bool = False,
        locator: CDispatch = None,
        wait_until_applied: bool = True,
        wait_until_applied_seconds: int = 15,
        verbose: bool = False,
        logger: Logger = None,
) -> tuple[list[str], list[str]] | None:
    """
    Add virtual IP addresses to the default network adapter.
    The adapter will set to static IP and DNS gateway, instead of dynamic DHCP.
    The first IPv4 address of the network_config will be used as VLAN and the unused IP addresses
    will be generated from it. Unused addresses decided by pinging them.
    Same for the subnet mask.

    While generating the IPs, the function will skip the already existing IPs in the adapter, like default gateway
    and DNS servers.

    :param interface_name: string, adapter name as shown in the network settings.

    :param number_of_ips: int, number of IPs to generate in addition to the IPv4s that already exist in the adapter.
        Or you add the IPs and masks to the adapter with the parameters virtual_ipv4s_to_add and virtual_ipv4_masks_to_add.

    :param virtual_ipv4s_to_add: list of strings, Add this IPv4 addresses to the current IPs of the adapter.
    :param virtual_ipv4_masks_to_add: list of strings, Add this subnet masks to the current subnet masks of the adapter.
        Or you generate the IPs and masks by specifying the number_of_ips parameter.

    :param set_virtual_ips_skip_as_source: bool, if True, the SkipAsSource flag will be set for the virtual IPs.
        This is needed to avoid the endless accept() loop.

    :param simulate_only: bool, if True, the function will only simulate the addition of the IP addresses.
        No changes will be made to the system.
    :param locator: CDispatch, WMI locator object. You can get it from:
        wrappers.pywin32s.wmis.wmi_helpers.get_wmi_instance()

    :param wait_until_applied: bool, if True, the function will wait until the IP addresses are applied.
        By default, while WMI command is executed, there is no indication if the addresses were finished applying or not.
        If you have 15+ addresses, it can take a while to apply them.
    :param wait_until_applied_seconds: int, seconds to wait for the IP addresses to be applied.
        This is different from availability_wait_seconds, which is the time to wait for the adapter to be available
        after setting the IP addresses. This is the time to wait for the IP addresses to be
        applied after setting them. If the IP addresses are not applied in this time, a TimeoutError will be raised.

    :param verbose: bool, if True, the function will print verbose output.
    :param logger: Logger, if provided, the function will log messages to this logger.

    :return: tuple of lists, (ips_to_assign, masks_to_assign)
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

    # Get the network adapter configuration.
    network_adapter_config, network_adapter, adapter_info = get_wmi_network_adapter_configuration(
        interface_name=interface_name, wmi_instance=wmi_civ2_instance, get_info_from_network_config=True)

    current_ipv4s: list[str] = adapter_info['ipv4s']
    current_ipv4_masks: list[str] = adapter_info['ipv4_subnet_masks']

    if number_of_ips > 0:
        ips_to_assign, masks_to_assign = generate_unused_ipv4_addresses_from_ip(
            ip_address=current_ipv4s[0],
            mask=current_ipv4_masks[0],
            number_of_ips=number_of_ips,
            skip_ips=current_ipv4s + adapter_info['default_gateways'] + adapter_info['dns_gateways']
        )
    elif virtual_ipv4s_to_add and virtual_ipv4_masks_to_add:
        ips_to_assign = virtual_ipv4s_to_add
        masks_to_assign = virtual_ipv4_masks_to_add
    else:
        ips_to_assign = []
        masks_to_assign = []

    if not simulate_only:
        # Enable DHCP + static IP coexistence on the interface.
        process_complete: subprocess.CompletedProcess = netshw.enable_dhcp_static_coexistence(interface_name=interface_name)
        if process_complete.returncode != 0:
            print_api(f"[!] Failed to enable DHCP + static IP coexistence on interface {interface_name}.\n"
                      f"    stdout: {process_complete.stdout}\n"
                      f"    stderr: {process_complete.stderr}", color="red", logger=logger)
            return None

        for ip, mask in zip(ips_to_assign, masks_to_assign):
            if verbose:
                print_api(f"[+] Adding virtual IP {ip} with mask {mask} to interface {interface_name}.", logger=logger)

            netshw.add_virtual_ip(
                interface_name=interface_name,
                ip=ip,
                mask=mask,
                skip_as_source=set_virtual_ips_skip_as_source
            )

        if wait_until_applied:
            # Wait until the IP addresses are applied.
            for _ in range(wait_until_applied_seconds):
                current_virtual_ips = get_interface_ips_powershell(interface_name=interface_name, ip_type="virtual")
                if set(current_virtual_ips) == set(ips_to_assign):
                    break
                time.sleep(1)
            else:
                raise TimeoutError("Timeout while waiting for the IP addresses to be applied.")

    return ips_to_assign, masks_to_assign


def wait_for_ip_bindable_socket(
    ip: str,
    port: int = 0,
    timeout: float = 15.0,
    interval: float = 0.5,
) -> None:
    """
    Wait until a single IP is bindable (or timeout).

    Raises TimeoutError if the IP cannot be bound within 'timeout' seconds.
    """

    socket_base.wait_for_ip_bindable(ip=ip, port=port, timeout=timeout, interval=interval)
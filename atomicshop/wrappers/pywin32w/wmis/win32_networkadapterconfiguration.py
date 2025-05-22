from typing import Union
import socket
import time

from win32com.client import CDispatch

from . import wmi_helpers, win32networkadapter
from ...psutilw import psutil_networks
from .... import ip_addresses


def get_network_configuration_by_adapter(
        adapter: CDispatch,
        wmi_instance: CDispatch = None
) -> Union[CDispatch, None]:
    """
    Get the network configuration for a specific adapter index.

    :param adapter: CDispatch, Win32_NetworkAdapter object.
    :param wmi_instance: WMI instance. You can get it from:
        wmi_helpers.get_wmi_instance()
    :return: Win32_NetworkAdapterConfiguration object.
    """

    network_config: CDispatch = wmi_instance.ExecQuery(
        f"SELECT * FROM Win32_NetworkAdapterConfiguration WHERE Index={adapter.Index}")[0]

    return network_config


def get_adapter_network_configuration(
        use_default_interface: bool = False,
        connection_name: str = None,
        mac_address: str = None,
        wmi_instance: CDispatch = None
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
    :return: tuple(Win32_NetworkAdapterConfiguration, Win32_NetworkAdapter)
    """

    if use_default_interface and connection_name:
        raise ValueError("Only one of 'use_default_interface' or 'connection_name' must be provided.")
    elif not use_default_interface and not connection_name:
        raise ValueError("Either 'use_default_interface' or 'connection_name' must be provided.")

    if not wmi_instance:
        wmi_instance, _ = wmi_helpers.get_wmi_instance()

    adapters = win32networkadapter.list_network_adapters(wmi_instance)

    current_adapter = None
    if use_default_interface:
        default_connection_name_dict: dict = psutil_networks.get_default_connection_name()
        if not default_connection_name_dict:
            raise wmi_helpers.WMINetworkAdapterNotFoundError("Default network adapter not found.")
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
            raise wmi_helpers.WMINetworkAdapterNotFoundError(f"Adapter with connection name '{connection_name}' not found.")
    elif mac_address:
        for adapter in adapters:
            if mac_address == adapter.MACAddress:
                current_adapter = adapter
                break

        if current_adapter is None:
            raise wmi_helpers.WMINetworkAdapterNotFoundError(f"Adapter with MAC address '{mac_address}' not found.")

    # Query the network adapter configurations
    query = f"SELECT * FROM Win32_NetworkAdapterConfiguration WHERE Index='{current_adapter.DeviceID}'"
    adapter_configs = wmi_instance.ExecQuery(query)

    # Check if the adapter exists
    if len(adapter_configs) == 0:
        raise wmi_helpers.WMINetworkAdapterNotFoundError(f"Adapter with connection name '{connection_name}' not found.")

    return adapter_configs[0], current_adapter


def set_static_ips(
        network_config: CDispatch,                               # Win32_NetworkAdapterConfiguration (CDispatch)
        ips: list[str],    # ["192.168.157.3", ...]
        masks: list[str],    # ["255.255.255.0", ...]
        gateways: list[str] = None,
        dns_gateways: list[str] = None,
        availability_wait_seconds: int = 0
) -> None:
    """
    • network_config      – Win32_NetworkAdapterConfiguration instance for the target NIC
                 (you already have it from GetObject / WMI query).
    • ips     – list of IPv4 strings.
    • masks    – matching subnet‑mask list (same length as ipv4).
    • gateways – list of default gateways (optional).
    • dns_gateways – list of DNS servers (optional).
    • availability_wait_seconds – seconds to wait for the adapter to become available.
        0 means no wait.

    Raises RuntimeError if Windows reports anything other than success (0 / 1)
    or "object already exists" (22) for each operation.

    ==========

    Example:
        cfg = wmi_instance.Get("Win32_NetworkAdapterConfiguration.Index=12")  # your adapter
        set_static_ips(
            cfg,
            ipv4=["192.168.157.129", "192.168.157.3", "192.168.157.4"],
            masks=["255.255.255.0"] * 3,
            # gateways=["192.168.157.2"],
            # dns_gateways=["8.8.8.8", "1.1.1.1"]
        )
    """

    initial_default_ipv4: str = socket.gethostbyname(socket.gethostname())

    # -------------------- IPv4 via EnableStatic ----------------------------
    if not masks or len(ips) != len(masks):
        raise ValueError("ipv4 and masks must be lists of equal length")

    in_params = network_config.Methods_("EnableStatic").InParameters.SpawnInstance_()
    in_params.IPAddress  = ips
    in_params.SubnetMask = masks

    rc = network_config.ExecMethod_("EnableStatic", in_params).Properties_('ReturnValue').Value
    if rc not in (0, 1):     # 0 = reboot required, 1 = OK
        raise RuntimeError(f"EnableStatic (IPv4) failed, code {rc}")

    # -------------------- Default Gateway via SetGateways -------------------
    if gateways:
        gateway_metrics = [1] * len(gateways)
        in_params = network_config.Methods_("SetGateways").InParameters.SpawnInstance_()
        in_params.DefaultIPGateway = gateways
        in_params.GatewayCostMetric = [int(m) for m in gateway_metrics]

        rc = network_config.ExecMethod_("SetGateways", in_params) \
            .Properties_('ReturnValue').Value
        if rc not in (0, 1):
            raise RuntimeError(f"SetGateways failed, code {rc}")

    # -------------------- DNS via SetDNSServerSearchOrder ------------------
    if dns_gateways:
        in_params = network_config.Methods_("SetDNSServerSearchOrder").InParameters.SpawnInstance_()
        in_params.DNSServerSearchOrder = dns_gateways

        rc = network_config.ExecMethod_("SetDNSServerSearchOrder", in_params).Properties_('ReturnValue').Value
        if rc not in (0, 1):
            raise RuntimeError(f"SetDNSServerSearchOrder failed, code {rc}")

    # -------------------- Wait for the adapter to become available -----------
    if availability_wait_seconds > 0:
        count = 0
        while count < 15:
            current_default_ipv4: str = socket.gethostbyname(socket.gethostname())
            if current_default_ipv4 == initial_default_ipv4:
                # print(f"[+] Adapter is available: {current_default_ipv4}")
                break
            else:
                # print(f"[!] Adapter is not available yet: [{current_default_ipv4}]")
                count += 1

            time.sleep(1)


def set_dynamic_ip(
        nic_cfg,
        reset_dns: bool = True,
        reset_wins: bool = True
) -> None:
    """
    Switch the adapter represented by *nic_cfg* (a Win32_NetworkAdapterConfiguration
    COM object) to DHCP.

    Parameters
    ----------
    nic_cfg : CDispatch
        The adapter’s Win32_NetworkAdapterConfiguration instance (IPEnabled = TRUE).
    reset_dns : bool, default True
        Also clear any static DNS servers (calls SetDNSServerSearchOrder(None)).
    reset_wins : bool, default True
        Also clear any static WINS servers (calls SetWINSServer(None, None)).

    Raises
    ------
    RuntimeError
        If any WMI call returns a status other than 0 (“Success”) or 1 (“Restart required”).
    """

    # 1) Turn on DHCP for IPv4
    wmi_helpers.call_method(nic_cfg, 'EnableDHCP')

    # 2) Clear static gateways (otherwise Windows keeps using them)
    wmi_helpers.call_method(nic_cfg, 'SetGateways', ([], []))    # empty SAFEARRAY → remove gateways

    # 3) Optional: reset DNS
    if reset_dns:
        wmi_helpers.call_method(nic_cfg, 'SetDNSServerSearchOrder', None)  # None = DHCP-provided DNS

    # 4) Optional: reset WINS
    if reset_wins:
        wmi_helpers.call_method(nic_cfg, 'SetWINSServer', ("", ""))


def get_info_from_network_config(
        network_config: CDispatch
) -> dict:
    """
    Collect information about adapter that currently carries the default route.

    :param network_config: CDispatch, Win32_NetworkAdapterConfiguration object.
    :return: dict of the default adapter.
    """

    def _split_ips(config):
        """Split IPAddress[] into separate v4 / v6 lists."""
        current_ipv4s: list[str] = []
        current_ipv4_masks: list[str] = []
        current_ipv6s: list[str] = []
        current_ipv6_prefixes: list[int] = []
        for address_index, ip_address in enumerate(config.IPAddress):
            if ip_addresses.is_ip_address(ip_address, 'ipv4'):
                current_ipv4s.append(ip_address)
                current_ipv4_masks.append(config.IPSubnet[address_index])
            elif ip_addresses.is_ip_address(ip_address, 'ipv6'):
                current_ipv6s.append(ip_address)
                current_ipv6_prefixes.append(int(config.IPSubnet[address_index]))

        return current_ipv4s, current_ipv6s, current_ipv4_masks, current_ipv6_prefixes

    ipv4s, ipv6s, ipv4subnets, ipv6prefixes = _split_ips(network_config)
    adapter = {
            "description": network_config.Description,
            "interface_index": network_config.InterfaceIndex,
            "is_dynamic": bool(network_config.DHCPEnabled),
            "ipv4s": ipv4s,
            "ipv6s": ipv6s,
            "ipv4_subnet_masks": ipv4subnets,
            "ipv6_prefixes": ipv6prefixes,
            "default_gateways": list(network_config.DefaultIPGateway or []),
            "dns_gateways": list(network_config.DNSServerSearchOrder or []),
        }

    return adapter
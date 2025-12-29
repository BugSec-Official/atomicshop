import subprocess
import re
from typing import List, Dict, Any, Optional

# ── regex helpers ─────────────────────────────────────────────────────────
IP_PATTERN        = r'(?:\d{1,3}\.){3}\d{1,3}'
RE_ADAPTER_HEADER = re.compile(r'Configuration for interface +"([^"]+)"', re.I)
RE_NUMERIC        = re.compile(r'\d+')
RE_SUBNET         = re.compile(rf'(?P<prefix>{IP_PATTERN}/\d+)\s+\(mask\s+(?P<mask>{IP_PATTERN})', re.I)
RE_IP             = re.compile(IP_PATTERN)


def get_netsh_show_config() -> str:
    """Run `netsh interface ipv4 show config` and return the raw text."""
    return subprocess.check_output(
        ["netsh", "interface", "ipv4", "show", "config"],
        text=True, encoding="utf-8", errors="ignore"
    )


# noinspection PyUnresolvedReferences
def get_netsh_ipv4() -> List[Dict[str, Any]]:
    """
    Parse *all* data from `netsh interface ipv4 show config`.

    Returns a list of dicts – one per adapter – with keys:
        interface, dhcp_enabled, ip_addresses, subnet_prefixes, subnet_masks,
        default_gateways, gateway_metric, interface_metric,
        dns_mode, dns_servers, wins_mode, wins_servers
    """
    config_text = get_netsh_show_config()

    adapters: List[Dict[str, Any]] = []
    adapter: Dict[str, Any] | None = None

    # Track whether we’re in continuation lines of DNS / WINS lists
    dns_list_type: str | None  = None   # 'static' | 'dynamic' | None
    wins_list_type: str | None = None

    for raw_line in config_text.splitlines():
        line = raw_line.strip()

        # 1) New adapter block ------------------------------------------------
        header_match = RE_ADAPTER_HEADER.search(line)
        if header_match:
            # Flush the previous adapter, if any
            if adapter:
                adapters.append(adapter)

            iface_name = header_match.group(1)
            adapter = {
                'interface_name'   : iface_name,
                'dhcp_enabled'     : None,
                'gateway_metric'   : None,
                'interface_metric' : None,
                'dns_mode'         : 'unknown',
                'wins_mode'        : 'unknown',
                'dns_servers'      : [],
                'wins_servers'     : [],
                'ip_addresses'     : [],
                'subnet_prefixes'  : [],
                'subnet_masks'     : [],
                'default_gateways' : [],
            }
            dns_list_type = wins_list_type = None
            continue

        if adapter is None:                 # skip prologue lines
            continue

        # 2) DHCP flag -------------------------------------------------------
        if line.startswith("DHCP enabled"):
            adapter['dhcp_enabled'] = "yes" in line.lower()
            continue

        # 3) IP addresses ----------------------------------------------------
        if line.startswith("IP Address"):
            adapter['ip_addresses'].extend(RE_IP.findall(line))
            continue

        # 4) Subnet prefix & mask -------------------------------------------
        if line.startswith("Subnet Prefix"):
            subnet_match = RE_SUBNET.search(line)
            if subnet_match:
                adapter['subnet_prefixes'].append(subnet_match.group('prefix'))
                adapter['subnet_masks'].append(subnet_match.group('mask'))
            continue

        # 5) Gateway & metrics ----------------------------------------------
        if line.startswith("Default Gateway"):
            adapter['default_gateways'].extend(RE_IP.findall(line))
            continue
        if line.startswith("Gateway Metric"):
            metric = RE_NUMERIC.search(line)
            if metric:
                adapter['gateway_metric'] = int(metric.group())
            continue
        if line.startswith("InterfaceMetric"):
            metric = RE_NUMERIC.search(line)
            if metric:
                adapter['interface_metric'] = int(metric.group())
            continue

        # 6) DNS header lines -----------------------------------------------
        if "DNS servers configured through DHCP" in line:
            adapter['dns_mode'] = 'dynamic'
            adapter['dns_servers'].extend(RE_IP.findall(line))
            dns_list_type = 'dynamic'
            continue
        if "Statically Configured DNS Servers" in line:
            adapter['dns_mode'] = 'static'
            adapter['dns_servers'].extend(RE_IP.findall(line))
            dns_list_type = 'static'
            continue

        # 7) WINS header lines ----------------------------------------------
        if "WINS servers configured through DHCP" in line:
            adapter['wins_mode'] = 'dynamic'
            adapter['wins_servers'].extend(RE_IP.findall(line))
            wins_list_type = 'dynamic'
            continue
        if line.startswith(("Primary WINS Server", "Secondary WINS Server")):
            adapter['wins_mode'] = 'static'
            adapter['wins_servers'].extend(RE_IP.findall(line))
            wins_list_type = 'static'
            continue

        # 8) Continuation lines for DNS / WINS -------------------------------
        if dns_list_type and RE_IP.search(line):
            adapter['dns_servers'].extend(RE_IP.findall(line))
            continue
        if wins_list_type and RE_IP.search(line):
            adapter['wins_servers'].extend(RE_IP.findall(line))
            continue

    # Flush the final adapter block
    if adapter:
        adapters.append(adapter)

    # # ── post-process: detect “mixed” modes ----------------------------------
    # NOT SURE THIS PART WORKS AS INTENDED!!!
    # for ad in adapters:
    #     if ad['dns_mode'] == 'dynamic' and ad['dns_servers']:
    #         # If both headers appeared the last one wins; treat that as mixed
    #         if any(k in ad['dns_servers'] for k in ad['default_gateways']):
    #             ad['dns_mode'] = 'mixed'
    #     if ad['wins_mode'] == 'dynamic' and ad['wins_servers']:
    #         if any(ip not in ad['wins_servers'] for ip in ad['wins_servers']):
    #             ad['wins_mode'] = 'mixed'

    return adapters


def run_netsh(*args: str) -> subprocess.CompletedProcess:
    """
    Run a netsh command and return stdout as text.

    Example:
        run_netsh("interface", "ipv4", "show", "interfaces")
    """
    cmd = ["netsh"] + list(args)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False
    )
    return result


def enable_dhcp_static_coexistence(interface_name: str) -> subprocess.CompletedProcess:
    """
    Enable DHCP + static IP coexistence on an interface.

    Equivalent to:
        netsh interface ipv4 set interface "Ethernet0" dhcpstaticipcoexistence=enabled
    """
    return run_netsh(
        "interface", "ipv4", "set", "interface",
        interface_name,
        "dhcpstaticipcoexistence=enabled"
    )


def disable_dhcp_static_coexistence(interface_name: str) -> subprocess.CompletedProcess:
    """
    Disable DHCP + static IP coexistence on an interface (optional).

    Equivalent to:
        netsh interface ipv4 set interface "Ethernet0" dhcpstaticipcoexistence=disabled
    """
    return run_netsh(
        "interface", "ipv4", "set", "interface",
        interface_name,
        "dhcpstaticipcoexistence=disabled"
    )


def add_virtual_ip(
        interface_name: str,
        ip: str,
        mask: str,
        skip_as_source: bool = True
) -> subprocess.CompletedProcess:
    """
    Add a static 'virtual' IP to a DHCP interface, keeping DHCP intact.

    Equivalent to:
        netsh interface ipv4 add address "Ethernet0" 192.168.1.201 255.255.255.0 skipassource=true

    Args:
        interface_name: Interface name, e.g. "Ethernet0"
        ip:     IP to add, e.g. "192.168.1.201"
        mask:   Subnet mask, e.g. "255.255.255.0"
        skip_as_source: If True, adds 'skipassource=true' so Windows does
                        not prefer this IP as the outbound source address.
    """
    args = [
        "interface", "ipv4", "add", "address",
        interface_name,
        ip,
        mask,
    ]
    if skip_as_source:
        args.append("skipassource=true")

    return run_netsh(*args)


def remove_virtual_ip(
        interface_name: str,
        ip: str
) -> subprocess.CompletedProcess:
    """
    Remove a previously added virtual IP from the interface.

    Equivalent to:
        netsh interface ipv4 delete address "Ethernet0" addr=192.168.1.201
    """
    return run_netsh(
        "interface", "ipv4", "delete", "address",
        interface_name,
        f"addr={ip}"
    )


def show_interface_config(
        interface_name: Optional[str] = None
) -> subprocess.CompletedProcess:
    """
    Show IPv4 configuration for all interfaces or a specific one.

    Equivalent to:
        netsh interface ipv4 show config
    or:
        netsh interface ipv4 show config "Ethernet0"
    """
    if interface_name:
        return run_netsh("interface", "ipv4", "show", "config", interface_name)
    else:
        return run_netsh("interface", "ipv4", "show", "config")


def list_ipv4_interfaces() -> subprocess.CompletedProcess:
    """
    List IPv4 interfaces.

    Equivalent to:
        netsh interface ipv4 show interfaces
    """
    return run_netsh("interface", "ipv4", "show", "interfaces")

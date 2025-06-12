import subprocess
import re
from typing import List, Dict, Any

# ── regex helpers ─────────────────────────────────────────────────────────
IP_PATTERN        = r'(?:\d{1,3}\.){3}\d{1,3}'
RE_ADAPTER_HEADER = re.compile(r'Configuration for interface +"([^"]+)"', re.I)
RE_NUMERIC        = re.compile(r'\d+')
RE_SUBNET         = re.compile(rf'(?P<prefix>{IP_PATTERN}/\d+)\s+\(mask\s+(?P<mask>{IP_PATTERN})', re.I)
RE_IP             = re.compile(IP_PATTERN)


def _get_netsh_show_config() -> str:
    """Run `netsh interface ipv4 show config` and return the raw text."""
    return subprocess.check_output(
        ["netsh", "interface", "ipv4", "show", "config"],
        text=True, encoding="utf-8", errors="ignore"
    )


def get_netsh_ipv4() -> List[Dict[str, Any]]:
    """
    Parse *all* data from `netsh interface ipv4 show config`.

    Returns a list of dicts – one per adapter – with keys:
        interface, dhcp_enabled, ip_addresses, subnet_prefixes, subnet_masks,
        default_gateways, gateway_metric, interface_metric,
        dns_mode, dns_servers, wins_mode, wins_servers
    """
    config_text = _get_netsh_show_config()

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

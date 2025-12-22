import json
import subprocess
from typing import List, Literal


def get_interface_ips(
    interface_name: str,
    ip_type: Literal["virtual", "dynamic", "all"] = "virtual"
) -> List[str]:
    """
    Return IPv4 addresses on an interface, filtered by 'mode'.

    ip_type:
      - "virtual": only static/virtual IPs (PrefixOrigin != 'Dhcp')
      - "dynamic": only DHCP IPs (PrefixOrigin == 'Dhcp')
      - "all":     all IPv4 IPs on the interface

    If the interface does not exist or has no IPv4 addresses, returns [].
    """

    ps_script = f"""
    try {{
        Get-NetIPAddress -InterfaceAlias "{interface_name}" -AddressFamily IPv4 |
            Select-Object IPAddress,
                          @{{
                              Name = 'PrefixOrigin';
                              Expression = {{ [string]$_.PrefixOrigin }}
                           }} |
            ConvertTo-Json -Depth 3
    }} catch {{
        # Return empty JSON array if nothing found / interface missing
        '[]'
    }}
    """

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        # If anything unexpected happens, raise a clearer error
        msg = (e.stderr or e.stdout or "").strip()
        raise RuntimeError(f"PowerShell Get-NetIPAddress failed: {msg}") from e

    stdout = result.stdout.strip()
    if not stdout:
        return []

    # At this point stdout should be valid JSON (list or single object)
    data = json.loads(stdout)

    if isinstance(data, dict):
        data = [data]

    ips: List[str] = []
    ip_type = ip_type.lower()

    for entry in data:
        ip = entry.get("IPAddress")
        origin_raw = entry.get("PrefixOrigin", "")
        origin = str(origin_raw).lower()

        if not ip:
            continue

        if ip_type == "virtual":
            if origin != "dhcp":
                ips.append(ip)
        elif ip_type == "dynamic":
            if origin == "dhcp":
                ips.append(ip)
        elif ip_type == "all":
            ips.append(ip)
        else:
            raise ValueError(f"Unsupported mode: {ip_type!r}")

    return ips
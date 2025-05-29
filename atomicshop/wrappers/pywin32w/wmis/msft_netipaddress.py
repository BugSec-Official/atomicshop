from typing import Optional

from win32com.client import CDispatch

from . import wmi_helpers


def set_skip_as_source(
        ip_addresses: list[str],
        enable: bool = True,
        wmi_instance: CDispatch = None
) -> None:
    """
    Toggle SkipAsSource for every address in *ip_addrs*.

    Parameters
    ----------
    ip_addresses : list/tuple/iterable of str
        One or more literal IP strings, e.g. "192.168.157.3"
    enable : bool
        True → behave like  Set‑NetIPAddress ‑SkipAsSource $true
        False → behave like Set‑NetIPAddress ‑SkipAsSource $false
    wmi_instance : CDispatch
        WMI instance to use. If not provided, a new one will be created.
        'root\\StandardCimv2'

    ================

    Explanation.
        When you add extra IPv4 addresses to the same NIC, Windows treats them all as “first‑class” unless you tell it otherwise.
        Because the two new addresses (192.168.157.3 and .4) are numerically lower than the original one (.129), the TCP/IP stack now prefers one of those lower addresses as the default source for any socket whose program didn’t bind an explicit local IP.

        What that looks like on the wire
        Client sends SYN → 192.168.157.3 (or .4).
        – Server replies with SYN/ACK ←192.168.157.3 → handshake completes, HTTP works.

        Client sends SYN → 192.168.157.129.
        – Stack still picks .3 as its favourite and answers SYN/ACK ← 192.168.157.3.
        – Client discards the packet (wrong IP), retransmits the SYN, your code’s accept() wakes up again, and you see an “infinite accept loop”.

        The flag that fixes it: SkipAsSource
        Tell Windows not to use the extra addresses unless an application asks for them.

        PowerShell.
        # One‑off: mark the addresses you already added
        Get-NetIPAddress -IPAddress 192.168.157.3 | Set-NetIPAddress -SkipAsSource $true
        Get-NetIPAddress -IPAddress 192.168.157.4 | Set-NetIPAddress -SkipAsSource $true

        # —OR— add new addresses the right way from the start
        New-NetIPAddress -InterfaceAlias "Ethernet0" `
                         -IPAddress 192.168.157.3 `
                         -PrefixLength 24 `
                         -SkipAsSource $true
        SkipAsSource = $true keeps the address fully routable for incoming traffic and lets programs bind to it explicitly.

        Windows will never choose that address as the source of an outgoing packet unless the program bound the socket to it.

        After you flip the flag (no reboot required) the three‑way handshake is symmetrical again and the endless accept() loop disappears.
    """

    if not wmi_instance:
        wmi_instance, _ = wmi_helpers.get_wmi_instance(namespace='root\\StandardCimv2')

    for ip in ip_addresses:
        query = f"SELECT * FROM MSFT_NetIPAddress WHERE IPAddress='{ip}'"
        matches = wmi_instance.ExecQuery(query)
        if not matches:
            print(f"[!] {ip}: no such address found")
            continue

        for obj in matches:                     # usually just one
            if bool(obj.SkipAsSource) == enable:
                print(f"[=] {ip}: SkipAsSource already {enable}")
                continue

            obj.SkipAsSource = enable
            obj.Put_()                          # commit the change
            print(f"[+] {ip}: SkipAsSource set to {enable}")


def is_skip_as_source(
        ip_address: str,
        wmi_instance: CDispatch = None
) -> Optional[bool]:
    """
    Check whether *ip_address* currently has SkipAsSource set.

    Returns
    -------
    True        – the flag is enabled
    False       – the flag is disabled
    None        – no MSFT_NetIPAddress object matches the IP (not present)

    Notes
    -----
    * Works for both IPv4/IPv6.
    * Uses the same Win32 CIM class (root\\StandardCimv2 › MSFT_NetIPAddress).
    * You can pass an existing `wmi_instance` to avoid reconnecting in tight loops.
    """
    # Get a WMI connection if the caller didn’t hand us one
    if not wmi_instance:
        wmi_instance, _ = wmi_helpers.get_wmi_instance(namespace='root\\StandardCimv2')

    query = f"SELECT SkipAsSource FROM MSFT_NetIPAddress WHERE IPAddress='{ip_address}'"
    matches = wmi_instance.ExecQuery(query)

    if not matches:                       # address not configured on this host/NIC
        return None

    # There should be only one entry per literal IP, but handle duplicates sanely
    # Return True if *any* matching record has SkipAsSource = True,
    # otherwise False (all are False).
    return any(bool(obj.SkipAsSource) for obj in matches)
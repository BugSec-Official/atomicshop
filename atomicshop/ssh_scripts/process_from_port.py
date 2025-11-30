#!/usr/bin/env python3
"""
Print the command line of the process that owns a given TCP/UDP source port.

Usage:
    python get_cmdline_from_port.py <port> [kind]

<port> is required (e.g. 54321)
[kind] is optional: 'tcp', 'udp', or 'inet' (default: 'inet')

Requires: psutil

===========================

In Ubuntu, you can check available TCP connections and processes with:
    ss -tnpa
In Windows, you can check available TCP connections and processes with (only PIDs, no command lines):
    netstat -ano
"""

import sys
import shlex
import psutil


def find_cmdline_by_port(
        port: int,
        # kind: str = "inet"
        kind: str = "tcp"
) -> str | None:
    """
    Return the command line (joined string) of the first process whose local
    port == `port`, for connections of type `kind` ('tcp', 'udp', 'inet', etc).

    'tcp' is much more specific and faster than 'inet' (which includes both TCP and UDP).
    """

    # Single system-wide call; 'inet' = IPv4 + IPv6 only (no unix sockets)
    # Use 'tcp' if you know it's TCP only – slightly faster.
    try:
        conns = psutil.net_connections(kind=kind)
    except psutil.Error:
        return None

    for conn in conns:
        # Some entries have no local address or PID (e.g. kernel sockets)
        laddr = conn.laddr
        if not laddr:
            continue

        # laddr is a namedtuple (ip, port) for AF_INET / AF_INET6
        try:
            local_port = laddr.port
        except AttributeError:
            # Older psutil: laddr is a simple tuple (ip, port)
            if len(laddr) < 2:
                continue
            local_port = laddr[1]

        if local_port != port:
            continue

        pid = conn.pid
        if pid is None or pid == 0:
            continue

        try:
            proc = psutil.Process(pid)
            cmdline_list = proc.cmdline()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

        if cmdline_list:
            result = shlex.join(cmdline_list)
        else:
            # Fallback to process name if cmdline missing
            try:
                result = proc.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                return None

        # If result is just a PID string, also fallback to name
        if result.isnumeric():
            try:
                result = proc.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                return None

        return result

    return None


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: get_cmdline_from_port.py <port> [kind]", file=sys.stderr)
        sys.exit(1)

    try:
        port = int(sys.argv[1])
    except ValueError:
        print("Port must be an integer", file=sys.stderr)
        sys.exit(1)

    kind = sys.argv[2] if len(sys.argv) >= 3 else "tcp"

    result = find_cmdline_by_port(port, kind)
    if result is not None:
        print(result)
        sys.exit(0)
    else:
        # Print nothing, or a message – up to you.
        # Empty output is often nicer for scripts that just parse stdout.
        # print(f"No process found with local port {port}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
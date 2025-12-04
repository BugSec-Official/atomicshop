#!/usr/bin/env python3
import argparse
import sys

import psutil


def _make_parser():
    parser = argparse.ArgumentParser(
        description="List all local TCP source ports currently in use that have a command line."
    )

    parser.add_argument(
        '-a', '--show-all', action='store_true',
        help='Show all the TCP ports and not only these that have command line.')

    return parser


def main(
    show_all: bool = False
) -> int:
    # Use a set so we only print each port once
    source_ports = set()

    try:
        # Get all TCP connections (any state)
        # If you only want established ones, use: kind='tcp' and filter by c.status
        connections = psutil.net_connections(kind='tcp')
    except psutil.AccessDenied:
        print("Access denied when reading connections. Try running as admin/root.")
        return 1
    except Exception as e:
        print(f"Error getting connections: {e}")
        return 1

    # Cache whether each PID has a non-empty cmdline to avoid repeated lookups
    pid_has_cmdline: dict[int, bool] = {}

    for c in connections:
        # c.laddr is the local (source) address; may be empty for some entries
        if not c.laddr:
            continue

        # psutil uses a namedtuple for laddr: (ip, port)
        try:
            port = c.laddr.port  # works on modern psutil (namedtuple)
        except AttributeError:
            # fallback if it's a plain tuple
            port = c.laddr[1]

        if not show_all:
            pid = c.pid
            if pid is None:
                # No associated process => treat as "no command line"
                continue

            if pid not in pid_has_cmdline:
                try:
                    proc = psutil.Process(pid)
                    cmdline = proc.cmdline()
                    # Non-empty list and at least one non-empty arg
                    has_cmd = bool(cmdline and any(arg.strip() for arg in cmdline))
                    pid_has_cmdline[pid] = has_cmd
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    # If we can't read it, treat as no command line
                    pid_has_cmdline[pid] = False

            if not pid_has_cmdline[pid]:
                # Skip ports whose owning process has an empty/unavailable cmdline
                continue

            # Either show_all is True, or the owning process has a non-empty cmdline
        source_ports.add(port)

    # Print ports sorted for readability
    for port in sorted(source_ports):
        print(port)

    return 0

if __name__ == "__main__":
    arg_parser = _make_parser()
    args = arg_parser.parse_args()
    sys.exit(main(**vars(args)))

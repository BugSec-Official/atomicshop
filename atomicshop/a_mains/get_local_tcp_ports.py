#!/usr/bin/env python3
import argparse
import platform
import re
import subprocess
import sys

import psutil


_LSOF_PORT_RE = re.compile(r":(\d+)$")


def _is_ubuntu() -> bool:
    if platform.system() != "Linux":
        return False
    try:
        with open("/etc/os-release", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("ID="):
                    value = line.split("=", 1)[1].strip().strip('"').lower()
                    return value == "ubuntu"
    except FileNotFoundError:
        return False
    except Exception:
        return False
    return False


def _lsof_cmd_has_cmdline(command: str) -> bool:
    if not command:
        return False
    # Kernel threads typically appear bracketed and have empty /proc/<pid>/cmdline
    if command.startswith("[") and command.endswith("]"):
        return False
    return True


def _parse_lsof_local_port(name_field: str):
    s = name_field.strip()
    if s.startswith("TCP "):
        s = s[4:]

    # Keep only the local endpoint portion, and drop state suffixes like "(LISTEN)"
    local = s.split("->", 1)[0].split(None, 1)[0]

    m = _LSOF_PORT_RE.search(local)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _main_lsof(show_all: bool = False) -> int:
    source_ports = set()

    cmd = ["sudo", "-n", "lsof", "-nP", "-iTCP", "-Fpcn"]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except Exception as e:
        print(f"Error running lsof: {e}")
        return 1

    if result.returncode != 0:
        msg = (result.stderr or result.stdout).strip()
        if "a password is required" in msg.lower() or "a terminal is required" in msg.lower():
            print(
                "sudo: a password is required to run lsof. "
                "Install lsof and add it to sudoers using scripts from 'tools/lsof/' directory.",
                file=sys.stderr
            )
        else:
            print(
                msg if msg else f"Error running lsof (exit code {result.returncode})",
                file=sys.stderr
            )
        return 1

    current_cmd = ""
    for line in result.stdout.splitlines():
        if not line:
            continue
        field = line[0]
        value = line[1:]
        if field == "c":
            current_cmd = value
        elif field == "n":
            port = _parse_lsof_local_port(value)
            if port is None:
                continue
            if show_all or _lsof_cmd_has_cmdline(current_cmd):
                source_ports.add(port)

    for port in sorted(source_ports):
        print(port)

    return 0


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

    if _is_ubuntu():
        return _main_lsof(show_all=show_all)

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

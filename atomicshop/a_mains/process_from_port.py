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

import os
import platform
import shlex
import subprocess
import sys

import psutil


def _is_ubuntu() -> bool:
    """
    Return True if running on Ubuntu (or Ubuntu-like via /etc/os-release).
    """
    if platform.system() != "Linux":
        return False

    try:
        with open("/etc/os-release", "r", encoding="utf-8") as f:
            data = f.read().lower()
    except OSError:
        return False

    # Common indicators
    # ID=ubuntu
    # ID_LIKE=debian
    # For WSL Ubuntu, this still typically shows ubuntu.
    return ("id=ubuntu" in data) or ("id_like=ubuntu" in data)


def _find_cmdline_by_port_psutil(port: int, kind: str = "tcp") -> str | None:
    """
    Original implementation: psutil.net_connections(kind=kind) scan.
    (Kept intact for Windows behavior.)
    """
    try:
        conns = psutil.net_connections(kind=kind)
    except psutil.Error:
        return None

    for conn in conns:
        laddr = conn.laddr
        if not laddr:
            continue

        try:
            local_port = laddr.port
        except AttributeError:
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
            try:
                result = proc.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                return None

        if result.isnumeric():
            try:
                result = proc.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                return None

        return result

    return None


def _read_proc_cmdline(pid: int) -> str | None:
    """
    Read and format a Linux process command line from /proc/<pid>/cmdline.
    Returns a shlex-joined string (quoted if needed), or None if unavailable.
    """
    cmdline_path = f"/proc/{pid}/cmdline"
    try:
        with open(cmdline_path, "rb") as f:
            raw = f.read()
    except OSError:
        raw = b""

    if raw:
        # cmdline is NUL-separated; last element may be empty
        parts = [p.decode(errors="replace") for p in raw.split(b"\x00") if p]
        if parts:
            return shlex.join(parts)

    # Fallback: /proc/<pid>/comm contains the short name
    comm_path = f"/proc/{pid}/comm"
    try:
        with open(comm_path, "r", encoding="utf-8", errors="replace") as f:
            comm = f.read().strip()
            return comm or None
    except OSError:
        return None


def _find_cmdline_by_port_ubuntu_lsof(port: int, kind: str = "tcp") -> str | None:
    """
    Ubuntu method (lsof-only on Ubuntu):
      1) Use lsof to find PID(s) that have a socket involving <kind>:<port>
      2) Read /proc/<pid>/cmdline and return the first command line found

    Notes:
      * kind supports: 'tcp', 'udp', 'inet'
      * Uses lsof -Q so "no matches" is not treated as an error exit code.
    """
    k = (kind or "").strip().lower()

    if k == "tcp":
        protos = ("TCP",)
    elif k == "udp":
        protos = ("UDP",)
    elif k == "inet":
        protos = ("TCP", "UDP")
    else:
        raise ValueError("On Ubuntu, kind must be one of: 'tcp', 'udp', 'inet' (lsof-only).")

    pids: list[int] = []
    seen: set[int] = set()

    for proto in protos:
        cmd = ["sudo", "-n", "lsof", "-nP", "-t", f"-i{proto}:{port}"]
        r = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if r.returncode == 0:
            out = r.stdout
        elif r.returncode == 1:
            # lsof commonly uses exit code 1 for "no matches".
            # But if sudo couldn't authenticate (password/TTY required), treat as an error.
            err = (r.stderr or "").lower()
            if "a password is required" in err or "a terminal is required" in err:
                sys.stderr.write(
                    "sudo: a password is required to run lsof. "
                    "Install lsof and add it to sudoers using scripts from 'tools/lsof/' directory.\n"
                )
                return None
            continue
        else:
            if r.stderr:
                sys.stderr.write(r.stderr)
            raise subprocess.CalledProcessError(r.returncode, cmd, output=r.stdout, stderr=r.stderr)

        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                pid = int(line)
            except ValueError:
                continue
            if pid not in seen:
                seen.add(pid)
                pids.append(pid)
                pids.append(pid)

    for pid in pids:
        cmdline = _read_proc_cmdline(pid)
        if cmdline:
            return cmdline

    return None


def find_cmdline_by_port(
        port: int,
        # kind: str = "inet"
        kind: str = "tcp"
) -> str | None:
    """
    Dispatch:
      - Windows: original psutil method
      - Ubuntu: lsof + /proc method (outputs only the command line)
      - Other OSes: original psutil method
    """
    if platform.system() == "Windows":
        return _find_cmdline_by_port_psutil(port, kind)

    if _is_ubuntu():
        return _find_cmdline_by_port_ubuntu_lsof(port, kind)

    return _find_cmdline_by_port_psutil(port, kind)


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

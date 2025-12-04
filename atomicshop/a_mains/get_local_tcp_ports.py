#!/usr/bin/env python3
import psutil

def main():
    # Use a set so we only print each port once
    source_ports = set()

    try:
        # Get all TCP connections (any state)
        # If you only want established ones, use: kind='tcp' and filter by c.status
        connections = psutil.net_connections(kind='tcp')
    except psutil.AccessDenied:
        print("Access denied when reading connections. Try running as admin/root.")
        return
    except Exception as e:
        print(f"Error getting connections: {e}")
        return

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

        source_ports.add(port)

    # Print ports sorted for readability
    for port in sorted(source_ports):
        print(port)

if __name__ == "__main__":
    main()

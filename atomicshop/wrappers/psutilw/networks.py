from typing import Union
import shlex
import socket

import psutil


def get_process_using_port(ip_port: str) -> Union[dict, None]:
    """
    Function to find the process using the port.
    :param ip_port: string, Listening IP and port number. Example: '192.168.0.1:443'
    :return: dict['pid', 'name', 'cmdline'] or None.
    """

    ip_address, port = ip_port.split(':')
    port = int(port)

    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            connections = proc.connections(kind='inet')
            for conn in connections:
                # if conn.laddr.port == port:
                # Status LISTEN is for TCP sockets and NONE is for UDP sockets.
                # Sometimes after socket close, the port will be in TIME_WAIT state.
                if conn.laddr.port == port and (conn.status == 'LISTEN' or conn.status == 'NONE'):
                    cmdline = proc.info['cmdline']
                    if not cmdline:
                        cmdline = '<EMPTY: TRY RUNNING AS ADMIN>'
                    else:
                        cmdline = shlex.join(cmdline)
                    return {
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cmdline': cmdline
                    }
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return None


def get_processes_using_port_list(ips_ports: list) -> Union[dict, None]:
    """
    Function to find the process using the port.
    :param ips_ports: List of listening ips and port numbers. Example:
        ['192.168.0.1:443', '192.168.0.2:443']
    :return: dict[port: {'pid', 'name', 'cmdline'}] or None.
    """
    port_process_map = {}
    for ip_port in ips_ports:
        process_info = get_process_using_port(ip_port)
        if process_info:
            port_process_map[ip_port] = process_info

    return port_process_map


def get_default_connection_name() -> Union[dict, None]:
    """
    Function to get the default network interface.
    :return: dict[interface_name: details] or None.
    """
    # Get all interfaces.
    interfaces: dict = psutil.net_if_addrs()
    default_ip_address: str = socket.gethostbyname(socket.gethostname())

    for interface, details in interfaces.items():
        for address in details:
            # Check if the address is an IPv4 address (AF_INET) and not a loopback (127.0.0.1)
            if address.family == socket.AF_INET and not address.address.startswith('127.'):
                # Check if the address is the default IP address.
                if address.address == default_ip_address:
                    return {interface: details}

    return None

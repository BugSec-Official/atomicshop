from typing import Union
import shlex
import socket

import psutil


def get_process_using_port(port: int) -> Union[dict, None]:
    """
    Function to find the process using the port.
    :param port: Port number.
    :return: dict['pid', 'name', 'cmdline'] or None.
    """
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


def get_processes_using_port_list(ports: list) -> Union[dict, None]:
    """
    Function to find the process using the port.
    :param ports: List of port numbers.
    :return: dict[port: {'pid', 'name', 'cmdline'}] or None.
    """
    port_process_map = {}
    for port in ports:
        process_info = get_process_using_port(port)
        if process_info:
            port_process_map[port] = process_info

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

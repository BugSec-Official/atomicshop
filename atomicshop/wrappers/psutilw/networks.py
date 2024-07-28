from typing import Union
import shlex

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
                if conn.laddr.port == port:
                    return {
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cmdline': shlex.join(proc.info['cmdline'])
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

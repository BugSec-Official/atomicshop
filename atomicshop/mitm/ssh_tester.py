import socket

import paramiko

from .. import package_mains_processor, ssh_remote, config_init
from ..wrappers.socketw import process_getter
from ..print_api import print_api


PORT_TO_CMD_FILE: str = 'process_from_port'
TCP_PORTS_FILE: str = 'get_local_tcp_ports'


def test_ssh_main(config: dict) -> int:
    hosts: list = config['main']['hosts_or_ips']

    for host in hosts:
        print("-----------------------------------")
        print_api(f"Testing cmd for host: {host}", color='blue')

        if host in config['main']:
            print("Using host-specific credentials")
            username = config[host]['user']
            password = config[host]['pass']
        else:
            print("Didn't find host-specific credential, using defaults")
            username = config['all_hosts']['user']
            password = config['all_hosts']['pass']

        ssh_client = ssh_remote.SSHRemote(ip_address=host, username=username, password=password)

        try:
            ssh_client.connect()
        except socket.gaierror as e:
            if e.errno == 11001:
                print_api(f"Couldn't resolve IP to {host}: {str(e)}\n"
                          f"Try providing IP address instead of hostname", color='red')
                continue
            else:
                raise e
        except paramiko.ssh_exception.NoValidConnectionsError as e:
            print_api(f"Couldn't connect to {host}: {str(e)}", color='red')
            continue

        # Read the TCP ports file to string.
        tcp_ports_package_processor: package_mains_processor.PackageMainsProcessor = package_mains_processor.PackageMainsProcessor(
            script_file_stem=TCP_PORTS_FILE)
        tcp_ports_script_string: str = tcp_ports_package_processor.read_script_file_to_string()

        # Execute the TCP ports script remotely via SSH to get the list of open TCP ports.
        tcp_ports_output, tcp_ports_error = ssh_client.remote_execution_python(script_string=tcp_ports_script_string)
        if tcp_ports_error:
            print_api(f"Error getting TCP ports from host {host}: {tcp_ports_error}", color='red')
            continue

        tcp_ports_list: list = tcp_ports_output.strip().splitlines()
        if not tcp_ports_list:
            print_api(f"No TCP ports found on host {host}", color='red')
            continue

        last_port: int = int(tcp_ports_list[-1])

        port_to_cmd_package_processor: package_mains_processor.PackageMainsProcessor = package_mains_processor.PackageMainsProcessor(
            script_file_stem=PORT_TO_CMD_FILE)
        get_command_instance = process_getter.GetCommandLine(
            client_ip=host,
            client_port=last_port,
            package_processor=port_to_cmd_package_processor,
            ssh_client=ssh_client)
        process_name = get_command_instance.get_process_name()
        print(f"Process for port {last_port} on host {host}: {process_name}")

        print("Closing SSH connection")
        ssh_client.close()

        if not process_name:
            print_api(f"Failed to get process name for port {last_port} on host {host}", color='red')
            continue

        print_api(f"SSH test success!", color='green')

    return 0

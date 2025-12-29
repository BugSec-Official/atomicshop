import os
import argparse
import base64

from ..print_api import print_api
from .. import networks, ssh_remote, package_mains_processor
from . import config_static, mitm_main


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply centered network settings to the target hosts based on the configuration file and arguments."
    )
    parser.add_argument(
        "-t", "--target-hosts-file",
        type=str,
        required=True,
        help="Path to the text file that will include the list of hosts (name/ipv4)."
    )

    parser.add_argument(
        "-dns", "--set-default-dns-gateway",
        action="store_true",
        help="Set the default gateway as this server LAN IPv4 on the target hosts."
    )
    parser.add_argument(
        "-ca", "--install-ca-cert",
        action="store_true",
        help="Install the CA certificate on the target hosts."
    )


    return parser


def centered_settings_main(config_file_path: str, script_version: str):
    print(f"Centered Settings Application Script Version: {script_version}")
    # Import the configuration file.
    rc: int = config_static.load_config(config_file_path, print_kwargs=dict(stdout=False))
    if rc != 0:
        return rc

    if config_static.MainConfig.is_localhost:
        print_api("The server is set to localhost mode. No changes will be applied.", color="yellow")
        return 0

    interface_name: str = mitm_main._get_interface_name()
    if interface_name is None:
        return 1

    # File path to the CA certificate file.
    crt_file_path: str = config_static.MainConfig.ca_certificate_crt_filepath
    with open(crt_file_path, 'r') as crt_file:
        ca_certificate_string: str = crt_file.read()

    # Get the main non-virtual IPv4 address.
    main_ipv4_list: list[str] = networks.get_interface_ips_powershell(interface_name, "dynamic")

    if not main_ipv4_list:
        print_api(f"Could not determine the main IPv4 address for interface: {interface_name}", color="red")
        return 1
    else:
        main_ipv4: str = main_ipv4_list[0]

    parser = _make_parser()
    args = parser.parse_args()

    target_hosts_file_path: str = args.target_hosts_file
    set_default_dns_gateway: bool = args.set_default_dns_gateway
    install_ca_cert: bool = args.install_ca_cert

    if not set_default_dns_gateway and not install_ca_cert:
        print_api("No actions specified. Use -dns and/or -ca arguments to apply settings.", color="yellow")
        return 0

    if not os.path.exists(target_hosts_file_path):
        print_api(f"Target host list file does not exist: {target_hosts_file_path}", color="red")
        return 1

    # Read the target hosts from the file.
    with open(target_hosts_file_path, 'r') as f:
        target_hosts: list[str] = [line.strip() for line in f if line.strip()]
    if not target_hosts:
        print_api(f"No target hosts found in the file: {target_hosts_file_path}", color="red")
        return 1

    if set_default_dns_gateway:
        package_processor: package_mains_processor.PackageMainsProcessor = package_mains_processor.PackageMainsProcessor(
            script_file_stem="set_default_dns_gateway")
    elif install_ca_cert:
        package_processor: package_mains_processor.PackageMainsProcessor = package_mains_processor.PackageMainsProcessor(
            script_file_stem="install_ca_certificate")
    else:
        print_api("No valid action specified.", color="red")
        return 1

    script_string: str = package_processor.read_script_file_to_string()

    for host in target_hosts:
        ssh_client = ssh_remote.SSHRemote(
            ip_address=host,
            username=config_static.ProcessName.ssh_user,
            password=config_static.ProcessName.ssh_pass
        )
        stderr = ssh_client.connect()
        if stderr:
            print_api(f"SSH connection to {host} failed:\n"
                      f"{stderr}", color="red")
            continue

        if set_default_dns_gateway:
            stdout, stderr = ssh_client.remote_execution_python(
                script_string=script_string, script_arg_values=(main_ipv4,))

            if stderr:
                print_api(f"Failed to apply settings on {host}:\n{stderr}", color="red")
            else:
                print_api(f"Successfully applied settings on {host}:\n{stdout}", color="green")
        elif install_ca_cert:
            cert_b64 = base64.b64encode(ca_certificate_string.encode("utf-8")).decode("ascii")
            stdout, stderr = ssh_client.remote_execution_python(
                script_string=script_string, script_arg_values=(config_static.MainConfig.ca_certificate_name, cert_b64,))

            if stderr:
                print_api(f"Failed to install CA certificate on {host}:\n{stderr}", color="red")
            else:
                print_api(f"Successfully installed CA certificate on {host}:\n{stdout}", color="green")

        # Closing SSH connection to the target host.
        ssh_client.close()


    return 0
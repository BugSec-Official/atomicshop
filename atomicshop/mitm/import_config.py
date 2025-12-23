import os
from pathlib import Path
import socket

from ..print_api import print_api
from .. import config_init, filesystem, dns
from ..permissions import permissions
from ..wrappers.socketw import socket_base
from ..basics import booleans

from . import config_static, initialize_engines


def import_config_files(
        config_file_path: str,
        print_kwargs: dict = None
):
    """
    Import the configuration file 'config.toml' and write all the values to 'config_static' dataclasses module.

    :param config_file_path:
    :param print_kwargs: dict, additional arguments to pass to the print function.
    :return:
    """

    config_toml: dict = config_init.get_config(
        script_directory=str(Path(config_file_path).parent),
        config_file_name=Path(config_file_path).name,
        print_kwargs=print_kwargs or {}
    )


    config_static.MainConfig.is_offline = bool(config_toml['dnstcp']['offline'])
    config_static.MainConfig.network_interface = config_toml['dnstcp']['network_interface']
    config_static.MainConfig.is_localhost = bool(config_toml['dnstcp']['localhost'])
    config_static.MainConfig.set_default_dns_gateway = config_toml['dnstcp']['set_default_dns_gateway']

    config_static.DNSServer.is_enabled = bool(config_toml['dns']['enable'])
    config_static.DNSServer.listening_ipv4 = config_toml['dns']['listening_ipv4']
    config_static.DNSServer.listening_port = config_toml['dns']['listening_port']
    config_static.DNSServer.forwarding_dns_service_ipv4 = config_toml['dns']['forwarding_dns_service_ipv4']
    config_static.DNSServer.cache_timeout_minutes = config_toml['dns']['cache_timeout_minutes']
    config_static.DNSServer.resolve_by_engine = bool(config_toml['dns']['resolve_by_engine'])
    config_static.DNSServer.resolve_regular_pass_thru = bool(config_toml['dns']['resolve_regular_pass_thru'])
    config_static.DNSServer.resolve_all_domains_to_ipv4 = config_toml['dns']['resolve_all_domains_to_ipv4']

    config_static.TCPServer.is_enabled = bool(config_toml['tcp']['enable'])
    config_static.TCPServer.no_engines_usage_to_listen_addresses = config_toml['tcp']['no_engines_usage_to_listen_addresses']

    config_static.LogRec.logs_path = config_toml['logrec']['logs_path']
    config_static.LogRec.enable_request_response_recordings_in_logs = bool(config_toml['logrec']['enable_request_response_recordings_in_logs'])
    config_static.LogRec.store_logs_for_x_days = config_toml['logrec']['store_logs_for_x_days']

    config_static.Certificates.install_ca_certificate_to_root_store = bool(config_toml['certificates']['install_ca_certificate_to_root_store'])
    config_static.Certificates.uninstall_unused_ca_certificates_with_mitm_ca_name = bool(config_toml['certificates']['uninstall_unused_ca_certificates_with_mitm_ca_name'])
    config_static.Certificates.default_server_certificate_usage = bool(config_toml['certificates']['default_server_certificate_usage'])
    config_static.Certificates.sni_add_new_domains_to_default_server_certificate = bool(config_toml['certificates']['sni_add_new_domains_to_default_server_certificate'])
    config_static.Certificates.custom_server_certificate_usage = bool(config_toml['certificates']['custom_server_certificate_usage'])
    config_static.Certificates.custom_server_certificate_path = config_toml['certificates']['custom_server_certificate_path']
    config_static.Certificates.custom_private_key_path = config_toml['certificates']['custom_private_key_path']
    config_static.Certificates.sni_create_server_certificate_for_each_domain = bool(config_toml['certificates']['sni_create_server_certificate_for_each_domain'])
    config_static.Certificates.sni_server_certificates_cache_directory = config_toml['certificates']['sni_server_certificates_cache_directory']
    config_static.Certificates.sni_get_server_certificate_from_server_socket = bool(config_toml['certificates']['sni_get_server_certificate_from_server_socket'])
    config_static.Certificates.sni_server_certificate_from_server_socket_download_directory = config_toml['certificates']['sni_server_certificate_from_server_socket_download_directory']

    config_static.SkipExtensions.tls_web_client_authentication = bool(config_toml['skip_extensions']['tls_web_client_authentication'])
    config_static.SkipExtensions.crl_distribution_points = bool(config_toml['skip_extensions']['crl_distribution_points'])
    config_static.SkipExtensions.authority_information_access = bool(config_toml['skip_extensions']['authority_information_access'])

    config_static.ProcessName.get_process_name = bool(config_toml['process_name']['get_process_name'])
    config_static.ProcessName.ssh_user = config_toml['process_name']['ssh_user']
    config_static.ProcessName.ssh_pass = config_toml['process_name']['ssh_pass']


    manipulations_after_import()

    result = import_engines_configs(print_kwargs=print_kwargs or {})
    if result != 0:
        return result

    result = check_configurations()
    return result


def import_engines_configs(print_kwargs: dict) -> int:
    """
    Import the engines configuration files and write all the values to 'config_static' dataclasses module.

    :return: int, status code.
    """

    # Get full paths of all the 'engine_config.ini' files.
    engine_config_path_list = filesystem.get_paths_from_directory(
        directory_path=config_static.MainConfig.ENGINES_DIRECTORY_PATH,
        get_file=True,
        file_name_check_pattern=config_static.MainConfig.ENGINE_CONFIG_FILE_NAME)

    # Iterate through all the 'engine_config.ini' file paths.
    domains_engine_list_full: list = list()
    engines_list: list = list()
    for engine_config_path in engine_config_path_list:
        # Initialize engine.
        current_module: initialize_engines.ModuleCategory = initialize_engines.ModuleCategory(config_static.MainConfig.SCRIPT_DIRECTORY)
        rc, error = current_module.fill_engine_fields_from_config(engine_config_path.path, print_kwargs=print_kwargs or {})
        if rc != 0:
            print_api(f"Error reading engine config file: {engine_config_path.path}\n{error}", color='red')
            return rc
        rc, error = current_module.initialize_engine(print_kwargs=print_kwargs or {})
        if rc != 0:
            print_api(f"Error initializing engine from directory: {Path(engine_config_path.path).parent}\n{error}", color='red')
            return rc

        # Extending the full engine domain list with this list.
        domains_engine_list_full.extend(current_module.domain_list)
        # Append the object to the engines list
        engines_list.append(current_module)
    # === EOF Importing engine modules =============================================================================
    # ==== Initialize Reference Module =============================================================================
    reference_module: initialize_engines.ModuleCategory = initialize_engines.ModuleCategory(config_static.MainConfig.SCRIPT_DIRECTORY)
    reference_module.fill_engine_fields_from_general_reference(config_static.MainConfig.ENGINES_DIRECTORY_PATH)
    result_code, error = reference_module.initialize_engine(reference_general=True)
    if result_code != 0:
        print_api(f"Error initializing reference engine from file: {config_static.MainConfig.ENGINES_DIRECTORY_PATH}\n{error}", color='red')
        return result_code

    # Assigning all the engines domains to all time domains, that will be responsible for adding new domains.
    domains_all_times_with_ports: list[str] = list(domains_engine_list_full)

    domains_all_times: list[str] = list()
    for domain_and_port in domains_all_times_with_ports:
        domain: str = domain_and_port.split(':')[0]
        if domain not in domains_engine_list_full:
            domains_all_times.append(domain)

    config_static.Certificates.domains_all_times = domains_all_times

    config_static.ENGINES_LIST = engines_list
    config_static.REFERENCE_MODULE = reference_module

    return 0


def check_configurations() -> int:
    """
    Check the configurations from the 'config.toml' file.
    If there are any errors, print them and return 1.
    :return: int, status code.
    """

    is_admin = permissions.is_admin()

    # Check if both DNS and TCP servers are disabled. ==============================================================
    if not config_static.DNSServer.is_enabled and not config_static.TCPServer.is_enabled:
        print_api("Both DNS and TCP servers in config ini file, nothing to run. Exiting...", color='red')
        return 1

    # Checking if listening interfaces were set.
    if not config_static.TCPServer.no_engines_usage_to_listen_addresses_enable:
        # If no engines were found, check if listening interfaces were set in the main config.
        if not config_static.ENGINES_LIST:
            message = (
                "\n"
                "No engines found. Create with [create_template.py].\n"
                "Exiting...")
            print_api(message, color="red")
            return 1
    else:
        if not config_static.TCPServer.no_engines_listening_address_list:
            message = (
                "\n"
                "No listening interfaces. Set [no_engines_usage_to_listen_addresses] in the main [config.toml].\n"
                "Exiting...")
            print_api(message, color="red")
            return 1

    if not config_static.ENGINES_LIST and config_static.DNSServer.resolve_by_engine:
        error_message = (
            f"No engines were found in: [{config_static.MainConfig.ENGINES_DIRECTORY_PATH}]\n"
            f"But the DNS routing is set to use them for routing.\n"
            f"Please check your DNS routing configuration in the [config.toml] file or create an engine with [create_template.py].")
        print_api(error_message, color="red")
        return 1

    for engine in config_static.ENGINES_LIST:
        port_list: list[str] = []
        for domain_port in engine.domain_list:
            # Check if the domains has port.
            if ':' not in domain_port:
                message = (
                    f"[*] Domain [{domain_port}] doesn't have a port.\n"
                    f"Please check your engine configuration file.")
                print_api(message, color="red")
                return 1
            else:
                # Split the domain and port.
                domain, port = domain_port.split(':')
                port_list.append(port)
                # Check if the port is a number.
                if not port.isdigit():
                    message = (
                        f"[*] Port [{port}] is not a number.\n"
                        f"Please check your engine configuration file.")
                    print_api(message, color="red")
                    return 1

        # Check if the ports in on_port_connect are unique.
        if engine.on_port_connect:
            ports_on_connect: list[str] = list(engine.on_port_connect.keys())
            # Check if any of the ports in the on_port_connect are not in the domain list.
            ports_in_domain_list: list[str] = []
            for port in ports_on_connect:
                if port in port_list:
                    ports_in_domain_list.append(port)

            if ports_in_domain_list:
                message = (
                    f"[*] Ports in [on_port_connect] config in engine_config.toml: {ports_in_domain_list}\n"
                    f"are also in the [domains] field.\n"
                    f"This is not supported.")
                print_api(message, color="red")
                return 1


    # Check admin right if on localhost ============================================================================
    # If any of the DNS IP target addresses is localhost loopback, then we need to check if the script
    # is executed with admin rights. There are some processes that 'psutil' can't get their command line if not
    # executed with administrative privileges.
    # Also, check Admin privileges only if 'config.tcp['get_process_name']' was set to 'True' in 'config.ini' of
    # the script.
    if config_static.ProcessName.get_process_name:
        # If the DNS server was set to resolve by engines, we need to check all relevant engine settings.
        if config_static.DNSServer.resolve_by_engine:
            # Check if the DNS target is localhost loopback.
            if config_static.MainConfig.is_localhost and not is_admin:
                message: str = \
                    ("Need to run the script with administrative rights to get the process name while TCP "
                     "running on the same computer.\nExiting...")
                print_api(message, color='red')
                return 1
        if config_static.DNSServer.resolve_all_domains_to_ipv4:
            if config_static.DNSServer.target_ipv4 in socket_base.THIS_DEVICE_IP_LIST or \
                    config_static.DNSServer.target_ipv4.startswith('127.'):
                if not is_admin:
                    message: str = \
                        ("Need to run the script with administrative rights to get the process name while TCP "
                         "running on the same computer.\nExiting...")
                    print_api(message, color='red')
                    return 1

    if (config_static.MainConfig.set_default_dns_gateway or
            config_static.MainConfig.set_default_dns_gateway_to_network_interface_ipv4):
        # Get current settings of the DNS gateway.
        is_dns_dynamic, current_dns_gateway = dns.get_default_dns_gateway()

        if not is_admin:
            if config_static.MainConfig.set_default_dns_gateway:
                ipv4_address_list = config_static.MainConfig.set_default_dns_gateway
            elif config_static.MainConfig.set_default_dns_gateway_to_network_interface_ipv4 and config_static.MainConfig.is_localhost:
                ipv4_address_list = [config_static.MainConfig.default_localhost_dns_gateway_ipv4]
            elif config_static.MainConfig.set_default_dns_gateway_to_network_interface_ipv4 and not config_static.MainConfig.is_localhost:
                ipv4_address_list = [socket.gethostbyname(socket.gethostname())]
            else:
                raise ValueError("Error: DNS gateway configuration is not set.")

            # If the setting is dynamic or static, but the needed target address is not in the current DNS gateway.
            if (is_dns_dynamic or
                    (not is_dns_dynamic and current_dns_gateway != ipv4_address_list)):
                status_string = 'Dynamic' if is_dns_dynamic else 'Static'
                message: str = (
                    "Need to run the script with administrative rights to set the default DNS gateway.\n"
                    f"Current DNS gateway: {status_string}, {current_dns_gateway}\n"
                    f"Target DNS gateway: Static, {ipv4_address_list}")
                print_api(message, color='red')
                return 1

    if not config_static.DNSServer.resolve_by_engine and not config_static.DNSServer.resolve_regular_pass_thru and not \
            config_static.DNSServer.resolve_all_domains_to_ipv4_enable:
        message: str = (
            "No DNS server resolving settings were set.\n"
            "Please check your DNS server settings in the [config.toml] file.")
        print_api(message, color='red')
        return 1

    # This is checked directly in the SocketWrapper.
    # if (config_static.Certificates.install_ca_certificate_to_root_store and not is_admin) or \
    #         (config_static.Certificates.uninstall_unused_ca_certificates_with_mitm_ca_name and not is_admin):
    #     message: str = \
    #         "Need to run the script with administrative rights to install or uninstall CA certificate.\nExiting..."
    #     print_api(message, color='red')
    #     return 1

    return 0


def manipulations_after_import():
    for key, value in config_static.DNSServer.resolve_all_domains_to_ipv4.items():
        key = bool(int(key))
        config_static.DNSServer.resolve_all_domains_to_ipv4_enable = key
        config_static.DNSServer.target_ipv4 = value
        break

    if config_static.MainConfig.set_default_dns_gateway:
        if config_static.MainConfig.set_default_dns_gateway[0] == 'l':
            config_static.MainConfig.set_default_dns_gateway_to_localhost = True
            config_static.MainConfig.set_default_dns_gateway = list()
        elif config_static.MainConfig.set_default_dns_gateway[0] == 'n':
            config_static.MainConfig.set_default_dns_gateway_to_network_interface_ipv4 = True
            config_static.MainConfig.set_default_dns_gateway = list()

    for key, value in config_static.TCPServer.no_engines_usage_to_listen_addresses.items():
        key = bool(int(key))
        # If the key is False, it means that the user doesn't want to use the no_engines_listening_address_list.
        # So, we'll assign an empty list to it.
        if not key:
            config_static.TCPServer.no_engines_usage_to_listen_addresses_enable = False
            config_static.TCPServer.no_engines_listening_address_list = list()
        # If the key is True, it means that the user wants to use the no_engines_listening_address_list.
        else:
            config_static.TCPServer.no_engines_usage_to_listen_addresses_enable = key
            config_static.TCPServer.no_engines_listening_address_list = value
        break

    # Convert extensions to skip to a list of extension IDs.
    skip_extensions: list = list()
    if config_static.SkipExtensions.tls_web_client_authentication:
        skip_extensions.append('1.3.6.1.5.5.7.3.2')
    if config_static.SkipExtensions.crl_distribution_points:
        skip_extensions.append('2.5.29.31')
    if config_static.SkipExtensions.authority_information_access:
        skip_extensions.append('1.3.6.1.5.5.7.1.1')
    config_static.SkipExtensions.SKIP_EXTENSION_ID_LIST = skip_extensions

    # If the paths are relative, convert them to absolute paths.
    config_static.LogRec.logs_path = filesystem.check_absolute_path___add_full(
        config_static.LogRec.logs_path, config_static.MainConfig.SCRIPT_DIRECTORY)
    config_static.Certificates.custom_server_certificate_path = filesystem.check_absolute_path___add_full(
        config_static.Certificates.custom_server_certificate_path, config_static.MainConfig.SCRIPT_DIRECTORY)

    config_static.LogRec.recordings_path = (
        config_static.LogRec.logs_path + os.sep + config_static.LogRec.recordings_directory_name)

    # At this point the user that sets the config can set it to null or empty string ''. We will make sure
    # that the path is None if it's empty.
    if config_static.Certificates.custom_private_key_path:
        config_static.Certificates.custom_private_key_path = filesystem.check_absolute_path___add_full(
            config_static.Certificates.custom_private_key_path, config_static.MainConfig.SCRIPT_DIRECTORY)
    else:
        # noinspection PyTypeChecker
        config_static.Certificates.custom_private_key_path = None

    config_static.Certificates.sni_server_certificates_cache_directory = filesystem.check_absolute_path___add_full(
        config_static.Certificates.sni_server_certificates_cache_directory, config_static.MainConfig.SCRIPT_DIRECTORY)
    config_static.Certificates.sni_server_certificate_from_server_socket_download_directory = \
        filesystem.check_absolute_path___add_full(
            config_static.Certificates.sni_server_certificate_from_server_socket_download_directory,
            config_static.MainConfig.SCRIPT_DIRECTORY)
    config_static.Certificates.sslkeylog_file_path = (f"{config_static.LogRec.logs_path}{os.sep}"
                                                      f"{config_static.Certificates.sslkeylog_file_name}")


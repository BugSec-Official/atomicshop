import os
from pathlib import Path
import socket

from ..print_api import print_api
from .. import config_init, filesystem, dns
from ..permissions import permissions
from ..wrappers.socketw import base
from ..basics import booleans

from . import config_static, initialize_engines


def assign_bool(dict_instance: dict, section: str, key: str):
    # If the value is already boolean, don't do anything.
    if dict_instance[section][key] is True or dict_instance[section][key] is False:
        return
    elif dict_instance[section][key] == 1:
        dict_instance[section][key] = True
    elif dict_instance[section][key] == 0:
        dict_instance[section][key] = False
    elif isinstance(dict_instance[section][key], dict):
        for subkey, subvalue in dict_instance[section][key].items():
            if subkey == '1':
                dict_instance[section][key] = {True: subvalue}
            elif subkey == '0':
                dict_instance[section][key] = {False: subvalue}
            else:
                print_api(f"Error: {section}.{key}.{subkey} must be 0 or 1.", color='red')
                return 1
            break
    else:
        print_api(f"Error: {section}.{key} must be 0 or 1.", color='red')
        return 1


def import_config_files(
        config_file_path: str
):
    """
    Import the configuration file 'config.toml' and write all the values to 'config_static' dataclasses module.

    :param config_file_path:
    :return:
    """

    config_toml: dict = config_init.get_config(
        script_directory=str(Path(config_file_path).parent), config_file_name=Path(config_file_path).name)

    # Assign boolean values to the toml dict module.
    for boolean_tuple in config_static.LIST_OF_BOOLEANS:
        assign_bool(config_toml, boolean_tuple[0], boolean_tuple[1])

    # Assign the configuration file content to the 'config_static' dataclasses module.
    for category, category_settings in config_toml.items():
        for setting_name, value in category_settings.items():
            # Get the dynamic class or dataclass from the 'config_static' module.
            dynamic_class = getattr(config_static, config_static.TOML_TO_STATIC_CATEGORIES[category])
            # Set the value to the dynamic class setting.
            setattr(dynamic_class, setting_name, value)

    manipulations_after_import()

    result = import_engines_configs()
    if result != 0:
        return result

    result = check_configurations()
    return result


def import_engines_configs() -> int:
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
        current_module.fill_engine_fields_from_config(engine_config_path.path)
        current_module.initialize_engine()

        # Extending the full engine domain list with this list.
        domains_engine_list_full.extend(current_module.domain_list)
        # Append the object to the engines list
        engines_list.append(current_module)
    # === EOF Importing engine modules =============================================================================
    # ==== Initialize Reference Module =============================================================================
    reference_module: initialize_engines.ModuleCategory = initialize_engines.ModuleCategory(config_static.MainConfig.SCRIPT_DIRECTORY)
    reference_module.fill_engine_fields_from_general_reference(config_static.MainConfig.ENGINES_DIRECTORY_PATH)
    reference_module.initialize_engine(reference_general=True)

    # Assigning all the engines domains to all time domains, that will be responsible for adding new domains.
    config_static.Certificates.domains_all_times = list(domains_engine_list_full)

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
    if not config_static.DNSServer.enable and not config_static.TCPServer.enable:
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

    is_localhost: bool | None = None
    for engine in config_static.ENGINES_LIST:
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
                # Check if the port is a number.
                if not port.isdigit():
                    message = (
                        f"[*] Port [{port}] is not a number.\n"
                        f"Please check your engine configuration file.")
                    print_api(message, color="red")
                    return 1

        # Check if 'localhost' is set in all the engines, or not.
        # There can't be mixed engines where local host is set and not set.
        # It can be all engines will be localhost or none of them.
        if is_localhost is None:
            is_localhost = engine.is_localhost
        else:
            if is_localhost != engine.is_localhost:
                message = (
                    f"[*] Mixed [localhost] setting in the engines found.\n"
                    f"[*] Some engines are set to [localhost] and some are not.\n"
                    f"[*] This is not allowed. All engines must be set to [localhost = 1] or All engines must be set to [localhost = 0].\n"
                    f"Please check your engine configuration files.")
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
            for engine in config_static.ENGINES_LIST:
                # Check if the DNS target is localhost loopback.
                if engine.dns_target in base.THIS_DEVICE_IP_LIST or engine.dns_target.startswith('127.'):
                    if not is_admin:
                        message: str = \
                            ("Need to run the script with administrative rights to get the process name while TCP "
                             "running on the same computer.\nExiting...")
                        print_api(message, color='red')
                        return 1
                if engine.no_sni.serve_domain_on_address_enable:
                    no_sni_target_address_list: list = engine.no_sni.serve_domain_on_address_dict.values()
                    for no_sni_target_address in no_sni_target_address_list:
                        if no_sni_target_address in base.THIS_DEVICE_IP_LIST or \
                                no_sni_target_address.startswith('127.'):
                            if not is_admin:
                                message: str = \
                                    ("Need to run the script with administrative rights to get the process name while TCP "
                                     "running on the same computer.\nExiting...")
                                print_api(message, color='red')
                                return 1
        if config_static.DNSServer.resolve_all_domains_to_ipv4:
            if config_static.DNSServer.target_ipv4 in base.THIS_DEVICE_IP_LIST or \
                    config_static.DNSServer.target_ipv4.startswith('127.'):
                if not is_admin:
                    message: str = \
                        ("Need to run the script with administrative rights to get the process name while TCP "
                         "running on the same computer.\nExiting...")
                    print_api(message, color='red')
                    return 1

    try:
        booleans.is_only_1_true_in_list(
            booleans_list_of_tuples=[
                (config_static.DNSServer.set_default_dns_gateway, '[dns][set_default_dns_gateway]'),
                (config_static.DNSServer.set_default_dns_gateway_to_localhost,
                 '[dns][set_default_dns_gateway_to_localhost]'),
                (config_static.DNSServer.set_default_dns_gateway_to_default_interface_ipv4,
                 '[dns][set_default_dns_gateway_to_default_interface_ipv4]')
            ],
            raise_if_all_false=False
        )
    except ValueError as e:
        print_api(str(e), color='red')
        return 1

    if (config_static.DNSServer.set_default_dns_gateway or
            config_static.DNSServer.set_default_dns_gateway_to_localhost or
            config_static.DNSServer.set_default_dns_gateway_to_default_interface_ipv4):
        # Get current settings of the DNS gateway.
        is_dns_dynamic, current_dns_gateway = dns.get_default_dns_gateway()

        if not is_admin:
            if config_static.DNSServer.set_default_dns_gateway:
                ipv4_address_list = config_static.DNSServer.set_default_dns_gateway
            elif config_static.DNSServer.set_default_dns_gateway_to_localhost:
                ipv4_address_list = ['127.0.0.1']
            elif config_static.DNSServer.set_default_dns_gateway_to_default_interface_ipv4:
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
        config_static.DNSServer.resolve_all_domains_to_ipv4_enable = key
        config_static.DNSServer.target_ipv4 = value
        break

    for key, value in config_static.TCPServer.no_engines_usage_to_listen_addresses.items():
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
        config_static.Certificates.custom_private_key_path = None

    config_static.Certificates.sni_server_certificates_cache_directory = filesystem.check_absolute_path___add_full(
        config_static.Certificates.sni_server_certificates_cache_directory, config_static.MainConfig.SCRIPT_DIRECTORY)
    config_static.Certificates.sni_server_certificate_from_server_socket_download_directory = \
        filesystem.check_absolute_path___add_full(
            config_static.Certificates.sni_server_certificate_from_server_socket_download_directory,
            config_static.MainConfig.SCRIPT_DIRECTORY)

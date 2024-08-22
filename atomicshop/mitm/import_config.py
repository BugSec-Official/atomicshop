import os
from pathlib import Path

from ..print_api import print_api
from .. import config_init, filesystem, dns
from ..permissions import permissions
from ..wrappers.socketw import base
from ..basics import booleans

from . import config_static


def assign_bool(dict_instance: dict, section: str, key: str):
    # If the value is already boolean, don't do anything.
    if dict_instance[section][key] is True or dict_instance[section][key] is False:
        return
    elif dict_instance[section][key] == 1:
        dict_instance[section][key] = True
    elif dict_instance[section][key] == 0:
        dict_instance[section][key] = False
    else:
        print_api(f"Error: {section}.{key} must be 0 or 1.", color='red')
        return 1


def import_config_file(
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

    result = check_configurations()
    return result


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

    # Check [tcp_server] boolean configurations. ===================================================================
    if not config_static.TCPServer.engines_usage and config_static.TCPServer.server_response_mode:
        message = "You can't set [server_response_mode = True], while setting\n" \
                    "[engines_usage = False].\n" \
                    "No engine modules will be loaded - so nothing to respond to.\n" \
                    "Exiting..."
        print_api(message, color='red')
        return 1

    # Check admin right if on localhost ============================================================================
    # If the 'config.dns['target_tcp_server_ipv4']' IP address is localhost, then we need to check if the script
    # is executed with admin rights. There are some processes that 'psutil' can't get their command line if not
    # executed with administrative privileges.
    # Also, check Admin privileges only if 'config.tcp['get_process_name']' was set to 'True' in 'config.ini' of
    # the script.
    if (config_static.DNSServer.target_tcp_server_ipv4 in base.THIS_DEVICE_IP_LIST and
            config_static.ProcessName.get_process_name):
        # If we're not running with admin rights, prompt to the user and make him decide what to do.
        # If he wants to continue running with 'psutil' exceptions or close the script and rerun with admin rights.
        if not is_admin:
            message: str = \
                ("Need to run the script with administrative rights to get the process name while TCP running "
                 "on the same computer.\nExiting...")
            print_api(message, color='red')
            return 1

    if config_static.DNSServer.set_default_dns_gateway or \
            config_static.DNSServer.set_default_dns_gateway_to_localhost or \
            config_static.DNSServer.set_default_dns_gateway_to_default_interface_ipv4:
        try:
            booleans.check_3_booleans_when_only_1_can_be_true(
                (config_static.DNSServer.set_default_dns_gateway, '[dns][set_default_dns_gateway]'),
                (config_static.DNSServer.set_default_dns_gateway_to_localhost,
                 '[dns][set_default_dns_gateway_to_localhost]'),
                (config_static.DNSServer.set_default_dns_gateway_to_default_interface_ipv4,
                 '[dns][set_default_dns_gateway_to_default_interface_ipv4]'))
        except ValueError as e:
            print_api(str(e), color='red')
            return 1

    if (config_static.DNSServer.set_default_dns_gateway or
            config_static.DNSServer.set_default_dns_gateway_to_localhost or
            config_static.DNSServer.set_default_dns_gateway_to_default_interface_ipv4):
        is_dns_dynamic, current_dns_gateway = dns.get_default_dns_gateway()
        if is_dns_dynamic and not is_admin:
            message: str = \
                "Need to run the script with administrative rights to set the default DNS gateway.\nExiting..."
            print_api(message, color='red')
            return 1

    return 0


def manipulations_after_import():
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

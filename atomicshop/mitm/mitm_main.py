import threading
import multiprocessing
import time
import datetime
import os
import logging

import atomicshop   # Importing atomicshop package to get the version of the package.

from .. import filesystem, on_exit, print_api, networks, dns
from ..permissions import permissions
from ..python_functions import get_current_python_version_string, check_python_version_compliance
from ..wrappers.socketw import socket_wrapper, dns_server, base
from ..wrappers.loggingw import loggingw
from ..wrappers.ctyping import win_console

from .connection_thread_worker import thread_worker_main
from . import config_static, recs_files


class NetworkSettings:
    """
    Class to store network settings.
    """

    def __init__(
            self,
            description: str | None = None,
            interface_index: int | None = None,
            is_dynamic: bool = False,
            ipv4s: list[str] = None,
            ipv6s: list[str] = None,
            ipv4_subnet_masks: list[str] = None,
            ipv6_prefixes: list[str] = None,
            default_gateways: list[str] = None,
            dns_gateways: list[str] = None
    ):

        self.description: str | None = description
        self.interface_index: int | None = interface_index
        self.is_dynamic: bool = is_dynamic
        self.ipv4s: list[str] = ipv4s if ipv4s is not None else list()
        self.ipv6s: list[str] = ipv6s if ipv6s is not None else list()
        self.ipv4_subnet_masks: list[str] = ipv4_subnet_masks if ipv4_subnet_masks is not None else list()
        self.ipv6_prefixes: list[str] = ipv6_prefixes if ipv6_prefixes is not None else list()
        self.default_gateways: list[str] = default_gateways if default_gateways is not None else list()
        self.dns_gateways: list[str] = dns_gateways if dns_gateways is not None else list()


# Global variables for setting the network interface to external IPs (eg: 192.168.0.1)
NETWORK_INTERFACE_SETTINGS: NetworkSettings = NetworkSettings()
CURRENT_IPV4S: list[str] = list()
CURRENT_IPV4_MASKS: list[str] = list()
IPS_TO_ASSIGN: list[str] = list()
MASKS_TO_ASSIGN: list[str] = list()

# Global variables for setting the network interface to localhost IPs (eg: 127.0.0.1), Only DNS gateway is set.
NETWORK_INTERFACE_IS_DYNAMIC: bool = bool()
NETWORK_INTERFACE_IPV4_ADDRESS_LIST: list[str] = list()
IS_SET_DNS_GATEWAY: bool = False


# noinspection PyTypeChecker
RECS_PROCESS_INSTANCE: multiprocessing.Process = None


EXCEPTIONS_CSV_LOGGER_NAME: str = 'exceptions'
EXCEPTIONS_CSV_LOGGER_HEADER: str = 'time,exception'
# noinspection PyTypeChecker
MITM_ERROR_LOGGER: loggingw.ExceptionCsvLogger = None

# Create logger's queue.
NETWORK_LOGGER_QUEUE: multiprocessing.Queue = multiprocessing.Queue()

# Create finalization queue for the rec archiving process.
FINALIZE_RECS_ARCHIVE_QUEUE: multiprocessing.Queue = multiprocessing.Queue()


try:
    win_console.disable_quick_edit()
except win_console.NotWindowsConsoleError:
    pass


def exit_cleanup():
    if config_static.ENGINES_LIST[0].is_localhost:
        if permissions.is_admin() and IS_SET_DNS_GATEWAY:
            is_dns_dynamic, current_dns_gateway = dns.get_default_dns_gateway()
            status_string = 'Dynamic' if is_dns_dynamic else 'Static'
            print_api.print_api(f'Current DNS Gateway: {status_string}, {current_dns_gateway}')

            if is_dns_dynamic != NETWORK_INTERFACE_IS_DYNAMIC or \
                    (not is_dns_dynamic and current_dns_gateway != NETWORK_INTERFACE_IPV4_ADDRESS_LIST):
                if NETWORK_INTERFACE_IS_DYNAMIC:
                    dns.set_connection_dns_gateway_dynamic(use_default_connection=True)
                else:
                    dns.set_connection_dns_gateway_static(
                        dns_servers=NETWORK_INTERFACE_IPV4_ADDRESS_LIST, use_default_connection=True)

                print_api.print_api("Returned default DNS gateway...", color='blue')
    else:
        # Get current network interface state.
        default_network_adapter_config, default_network_adapter, default_adapter_info = networks.get_wmi_network_adapter_configuration(
            use_default_interface=True, get_info_from_network_config=True)

        if NETWORK_INTERFACE_SETTINGS.is_dynamic:
            # If the network interface was dynamic before the script started, we will return it to dynamic.
            networks.set_dynamic_ip_for_adapter(default_network_adapter_config)
        else:
            networks.set_static_ip_for_adapter(
                default_network_adapter,
                ips=NETWORK_INTERFACE_SETTINGS.ipv4s,
                masks=NETWORK_INTERFACE_SETTINGS.ipv4_subnet_masks,
                gateways=NETWORK_INTERFACE_SETTINGS.default_gateways,
                dns_gateways=NETWORK_INTERFACE_SETTINGS.dns_gateways
            )

        print_api.print_api("Returned network adapter settings...", color='blue')

    # The process will not be executed if there was an exception in the beginning.
    if RECS_PROCESS_INSTANCE is not None:
        print_api.print_api(f'Recs archive process alive: {RECS_PROCESS_INSTANCE.is_alive()}')
        RECS_PROCESS_INSTANCE.terminate()
        RECS_PROCESS_INSTANCE.join()

    # Before terminating multiprocessing child processes, we need to put None to all the QueueListeners' queues,
    # so they will stop waiting for new logs and will be able to terminate.
    # Or else we will get a BrokenPipeError exception. This happens for because the QueueListener is waiting for
    # new logs to come through the ".get()" method, but the main process is already terminated.
    NETWORK_LOGGER_QUEUE.put(None)
    # Get all the child processes and terminate them.
    for process in multiprocessing.active_children():
        process.terminate()
        # We need for processes to finish, since there is a logger there that needs to write the last log.
        process.join()


def startup_output(system_logger, script_version: str):
    """
    The function outputs the startup information to the console.
    """

    # Writing first log.
    system_logger.info("======================================")
    system_logger.info("Server Started.")
    system_logger.info(f"Python Version: {get_current_python_version_string()}")
    system_logger.info(f"Script Version: {script_version}")
    system_logger.info(f"Atomic Workshop Version: {atomicshop.__version__}")
    system_logger.info(f"Log folder: {config_static.LogRec.logs_path}")
    if config_static.LogRec.enable_request_response_recordings_in_logs:
        system_logger.info(f"Recordings folder for Requests/Responses: {config_static.LogRec.recordings_path}")
    system_logger.info(f"Loaded system logger: {system_logger}")

    # Some 'config.ini' settings logging ===========================================================================
    if config_static.Certificates.default_server_certificate_usage:
        system_logger.info(
            f"Default server certificate usage enabled, if no SNI available: "
            f"{config_static.MainConfig.default_server_certificate_filepath}")

    if config_static.Certificates.sni_server_certificates_cache_directory:
        system_logger.info(
            f"SNI function certificates creation enabled. Certificates cache: "
            f"{config_static.Certificates.sni_server_certificates_cache_directory}")
    else:
        system_logger.info(f"SNI function certificates creation disabled.")

    if config_static.Certificates.custom_server_certificate_usage:
        system_logger.info(f"Custom server certificate usage is enabled.")
        system_logger.info(f"Custom Certificate Path: {config_static.Certificates.custom_server_certificate_path}")

        # If 'custom_private_key_path' field was populated.
        if config_static.Certificates.custom_private_key_path:
            system_logger.info(
                f"Custom Certificate Private Key Path: {config_static.Certificates.custom_private_key_path}")
        else:
            system_logger.info(f"Custom Certificate Private Key Path wasn't provided in [advanced] section. "
                               f"Assuming the private key is inside the certificate file.")

    # === Engine logging ===========================================================================================
    # Printing the parsers using "start=1" for index to start counting from "1" and not "0"
    system_logger.info("Imported engine info.")
    print_api.print_api(f"[*] Found Engines:", logger=system_logger)

    if not config_static.ENGINES_LIST:
        message = \
            f"No engines found, the TCP server will use general response engine for all the input domains."
        print_api.print_api(message, color="blue", logger=system_logger)

    for index, engine in enumerate(config_static.ENGINES_LIST, start=1):
        message = f"[*] {index}: {engine.engine_name} | {engine.domain_list}"
        print_api.print_api(message, logger=system_logger)

        message = (f"[*] Modules: {engine.parser_class_object.__name__}, "
                   f"{engine.responder_class_object.__name__}, "
                   f"{engine.recorder_class_object.__name__}")
        print_api.print_api(message, logger=system_logger)
        print_api.print_api(f"[*] Name: {engine.engine_name}", logger=system_logger)
        print_api.print_api(f"[*] Domains: {list(engine.domain_target_dict.keys())}", logger=system_logger)
        dns_targets: list = list()
        for domain, ip_port in engine.domain_target_dict.items():
            dns_targets.append(ip_port['ip'])
        print_api.print_api(f"[*] DNS Targets: {dns_targets}", logger=system_logger)

        if engine.on_port_connect:
            print_api.print_api(f"[*] Connect Ports to IPs: {list(engine.on_port_connect.values())}", logger=system_logger)
            print_api.print_api(f"[*] Connect Ports to IPs Targets: {list(engine.port_target_dict.values())}", logger=system_logger)

        # print_api.print_api(f"[*] TCP Listening Interfaces: {engine.tcp_listening_address_list}", logger=system_logger)

    if config_static.DNSServer.enable:
        print_api.print_api("DNS Server is enabled.", logger=system_logger)

        # If engines were found and dns is set to route by the engine domains.
        if config_static.ENGINES_LIST and config_static.DNSServer.resolve_by_engine:
            print_api.print_api(
                "Engine domains will be routed by the DNS server to Built-in TCP Server.", logger=system_logger)
        # If engines were found, but the dns isn't set to route to engines.
        elif config_static.ENGINES_LIST and not config_static.DNSServer.resolve_by_engine:
            message = f"[*] Engines found, but the DNS routing is set not to use them for routing."
            print_api.print_api(message, color="yellow", logger=system_logger)

        if config_static.DNSServer.resolve_all_domains_to_ipv4_enable:
            print_api.print_api(
                f"All domains will be routed by the DNS server to Built-in TCP Server: [{config_static.DNSServer.target_ipv4}]",
                color="blue", logger=system_logger)

        if config_static.DNSServer.resolve_regular_pass_thru:
            print_api.print_api(
                "Regular DNS resolving is enabled. Built-in TCP server will not be routed to",
                logger=system_logger, color="yellow")
    else:
        print_api.print_api("DNS Server is disabled.", logger=system_logger, color="yellow")

    if config_static.TCPServer.enable:
        print_api.print_api("TCP Server is enabled.", logger=system_logger)
    else:
        print_api.print_api("TCP Server is disabled.", logger=system_logger, color="yellow")


def get_ipv4s_for_tcp_server():
    """
    Function to get the IPv4 addresses for the default network adapter to set them to the adapter.
    """

    # Create a list of all the domains in all the engines.
    domains_to_create_ips_for: list[str] = list()
    ports_to_create_ips_for: list[str] = list()
    for engine in config_static.ENGINES_LIST:
        domains_to_create_ips_for += list(engine.domain_target_dict.keys())
        ports_to_create_ips_for += list(engine.on_port_connect.keys())

    engine_ips: list[str] = list()
    # Check if we need the localhost ips (12.0.0.1) or external local ips (192.168.0.100).
    if config_static.ENGINES_LIST[0].is_localhost:
        create_ips: int = len(domains_to_create_ips_for) + len(ports_to_create_ips_for)

        # Generate the list of localhost ips.
        for i in range(create_ips):
            engine_ips.append(f"127.0.0.{i+1}")
    else:
        # Get current network interface state.
        default_network_adapter_config, default_network_adapter, default_adapter_info = networks.get_wmi_network_adapter_configuration(
            use_default_interface=True, get_info_from_network_config=True)

        global NETWORK_INTERFACE_SETTINGS
        NETWORK_INTERFACE_SETTINGS = NetworkSettings(
            description=default_adapter_info['description'],
            interface_index=default_adapter_info['interface_index'],
            is_dynamic=default_adapter_info['is_dynamic'],
            ipv4s=default_adapter_info['ipv4s'],
            ipv6s=default_adapter_info['ipv6s'],
            ipv4_subnet_masks=default_adapter_info['ipv4_subnet_masks'],
            ipv6_prefixes=default_adapter_info['ipv6_prefixes'],
            default_gateways=default_adapter_info['default_gateways'],
            dns_gateways=default_adapter_info['dns_gateways']
        )

        # Adding IP addresses to the default network adapter.
        current_ipv4s: list[str] = default_adapter_info['ipv4s']
        current_ips_count: int = len(current_ipv4s)

        # If the number of currently assigned IPs is smaller than the number of IPs to create,
        # subtract the current IPs count from the number of IPs to create, to create only what is missing.
        create_ips: int = len(domains_to_create_ips_for)
        if current_ips_count <= create_ips:
            create_ips -= current_ips_count

        # Generate the IPs for the domains.
        global CURRENT_IPV4S, CURRENT_IPV4_MASKS, IPS_TO_ASSIGN, MASKS_TO_ASSIGN
        CURRENT_IPV4S, CURRENT_IPV4_MASKS, IPS_TO_ASSIGN, MASKS_TO_ASSIGN = networks.add_virtual_ips_to_default_adapter_by_current_setting(
            number_of_ips=create_ips,
            simulate_only=True)

        engine_ips += CURRENT_IPV4S + IPS_TO_ASSIGN

    # Add the ips to engines.
    for engine in config_static.ENGINES_LIST:
        for domain in engine.domain_target_dict.keys():
            # If the domain is in the list of domains to create IPs for, add the IP to the engine.
            if domain in domains_to_create_ips_for:
                engine.domain_target_dict[domain]['ip'] = engine_ips.pop(0)
        for port in engine.on_port_connect.keys():
            # If the port is in the list of ports to create IPs for, add the IP to the engine.
            if port in ports_to_create_ips_for:
                engine.port_target_dict[port]['ip'] = engine_ips.pop(0)

def mitm_server(config_file_path: str, script_version: str):
    on_exit.register_exit_handler(exit_cleanup, at_exit=False, kill_signal=False)

    # Main function should return integer with error code, 0 is successful.
    # Since listening server is infinite, this will not be reached.
    # After modules import - we check for python version.
    if not check_python_version_compliance(minor_version='3.12'):
        return 1

    # Import the configuration file.
    result = config_static.load_config(config_file_path)
    if result != 0:
        return result

    # Get the IPs that will be set for the adapter and fill the engine configuration with the IPs.
    get_ipv4s_for_tcp_server()

    global MITM_ERROR_LOGGER
    MITM_ERROR_LOGGER = loggingw.ExceptionCsvLogger(
        logger_name=EXCEPTIONS_CSV_LOGGER_NAME, directory_path=config_static.LogRec.logs_path)

    # Create folders.
    filesystem.create_directory(config_static.LogRec.logs_path)

    if config_static.Certificates.sni_get_server_certificate_from_server_socket:
        filesystem.create_directory(
            config_static.Certificates.sni_server_certificate_from_server_socket_download_directory)

    network_logger_name = config_static.MainConfig.LOGGER_NAME

    # If we exit the function, we need to stop the listener: network_logger_queue_listener.stop()
    network_logger_queue_listener = loggingw.create_logger(
        get_queue_listener=True,
        log_queue=NETWORK_LOGGER_QUEUE,
        file_path=f'{config_static.LogRec.logs_path}{os.sep}{network_logger_name}.txt',
        add_stream=True,
        add_timedfile=True,
        formatter_streamhandler='DEFAULT',
        formatter_filehandler='DEFAULT',
        backupCount=config_static.LogRec.store_logs_for_x_days)

    network_logger_with_queue_handler: logging.Logger = loggingw.create_logger(
        logger_name=network_logger_name,
        add_queue_handler=True,
        log_queue=NETWORK_LOGGER_QUEUE)

    # Initiate Listener logger, which is a child of network logger, so he uses the same settings and handlers
    listener_logger: logging.Logger = loggingw.get_logger_with_level(f'{network_logger_name}.listener')
    system_logger: logging.Logger = loggingw.get_logger_with_level(f'{network_logger_name}.system')

    if config_static.LogRec.enable_request_response_recordings_in_logs:
        filesystem.create_directory(config_static.LogRec.recordings_path)
        # Compress recordings of the previous days if there are any.
        global RECS_PROCESS_INSTANCE
        RECS_PROCESS_INSTANCE = recs_files.recs_archiver_in_process(
            config_static.LogRec.recordings_path,
            logging_queue=NETWORK_LOGGER_QUEUE,
            logger_name=network_logger_name,
            finalize_output_queue=FINALIZE_RECS_ARCHIVE_QUEUE
        )

        archiver_result = FINALIZE_RECS_ARCHIVE_QUEUE.get()
        if isinstance(archiver_result, Exception):
            print_api.print_api(
                f"Error while archiving recordings: {archiver_result}",
                error_type=True, color="red", logger=system_logger, logger_method='critical')
            # Wait for the message to be printed and saved to file.
            time.sleep(1)
            network_logger_queue_listener.stop()
            return 1

    # Logging Startup information.
    startup_output(system_logger, script_version)

    print_api.print_api("Press [Ctrl]+[C] to stop.", color='blue')

    # === Initialize DNS module ====================================================================================
    if config_static.DNSServer.enable:
        dns_process = multiprocessing.Process(
            target=dns_server.start_dns_server_multiprocessing_worker,
            kwargs={
                'listening_address': config_static.DNSServer.listening_address,
                'log_directory_path': config_static.LogRec.logs_path,
                'backupCount_log_files_x_days': config_static.LogRec.store_logs_for_x_days,
                'forwarding_dns_service_ipv4': config_static.DNSServer.forwarding_dns_service_ipv4,
                'forwarding_dns_service_port': config_static.DNSServer.forwarding_dns_service_port,
                'resolve_by_engine': (
                    config_static.DNSServer.resolve_by_engine, config_static.ENGINES_LIST),
                'resolve_regular_pass_thru': config_static.DNSServer.resolve_regular_pass_thru,
                'resolve_all_domains_to_ipv4': (
                    config_static.DNSServer.resolve_all_domains_to_ipv4_enable, config_static.DNSServer.target_ipv4),
                'offline_mode': config_static.MainConfig.offline,
                'cache_timeout_minutes': config_static.DNSServer.cache_timeout_minutes,
                'logging_queue': NETWORK_LOGGER_QUEUE,
                'logger_name': network_logger_name
            },
            name="dns_server")
        dns_process.daemon = True
        dns_process.start()

        # Wait for the DNS server to start and do the port test.
        is_alive: bool = False
        max_wait_time: int = 5
        while not is_alive:
            is_alive = dns_process.is_alive()
            time.sleep(1)
            max_wait_time -= 1
            if max_wait_time == 0:
                message = "DNS Server process didn't start."
                print_api.print_api(message, error_type=True, color="red", logger=system_logger)
                # Wait for the message to be printed and saved to file.
                time.sleep(1)
                network_logger_queue_listener.stop()
                return 1

        # Now we can check if the process wasn't terminated after the check.
        max_wait_time: int = 5
        while max_wait_time > 0:
            is_alive = dns_process.is_alive()

            if not is_alive:
                message = "DNS Server process terminated."
                print_api.print_api(message, error_type=True, color="red", logger=system_logger)
                # Wait for the message to be printed and saved to file.
                time.sleep(1)
                network_logger_queue_listener.stop()
                return 1

            time.sleep(1)
            max_wait_time -= 1

    # === EOF Initialize DNS module ================================================================================
    # === Initialize TCP Server ====================================================================================
    if config_static.TCPServer.enable:
        try:
            socket_wrapper_instance = socket_wrapper.SocketWrapper(
                ca_certificate_name=config_static.MainConfig.ca_certificate_name,
                ca_certificate_filepath=config_static.MainConfig.ca_certificate_filepath,
                ca_certificate_crt_filepath=config_static.MainConfig.ca_certificate_crt_filepath,
                install_ca_certificate_to_root_store=config_static.Certificates.install_ca_certificate_to_root_store,
                uninstall_unused_ca_certificates_with_ca_certificate_name=(
                    config_static.Certificates.uninstall_unused_ca_certificates_with_mitm_ca_name),
                default_server_certificate_usage=config_static.Certificates.default_server_certificate_usage,
                default_server_certificate_name=config_static.MainConfig.default_server_certificate_name,
                default_certificate_domain_list=config_static.Certificates.domains_all_times,
                default_server_certificate_directory=config_static.MainConfig.SCRIPT_DIRECTORY,
                sni_use_default_callback_function=True,
                sni_use_default_callback_function_extended=True,
                sni_add_new_domains_to_default_server_certificate=(
                    config_static.Certificates.sni_add_new_domains_to_default_server_certificate),
                sni_create_server_certificate_for_each_domain=(
                    config_static.Certificates.sni_create_server_certificate_for_each_domain),
                sni_server_certificates_cache_directory=(
                    config_static.Certificates.sni_server_certificates_cache_directory),
                sni_get_server_certificate_from_server_socket=(
                    config_static.Certificates.sni_get_server_certificate_from_server_socket),
                sni_server_certificate_from_server_socket_download_directory=(
                    config_static.Certificates.sni_server_certificate_from_server_socket_download_directory),
                custom_server_certificate_usage=config_static.Certificates.custom_server_certificate_usage,
                custom_server_certificate_path=config_static.Certificates.custom_server_certificate_path,
                custom_private_key_path=config_static.Certificates.custom_private_key_path,
                get_process_name=config_static.ProcessName.get_process_name,
                ssh_user=config_static.ProcessName.ssh_user,
                ssh_pass=config_static.ProcessName.ssh_pass,
                ssh_script_to_execute=config_static.ProcessName.ssh_script_to_execute,
                logger=listener_logger,
                exceptions_logger=MITM_ERROR_LOGGER,
                statistics_logs_directory=config_static.LogRec.logs_path,
                forwarding_dns_service_ipv4_list___only_for_localhost=[config_static.DNSServer.forwarding_dns_service_ipv4],
                skip_extension_id_list=config_static.SkipExtensions.SKIP_EXTENSION_ID_LIST,
                no_engine_usage_enable=config_static.TCPServer.no_engines_usage_to_listen_addresses_enable,
                no_engines_listening_address_list=config_static.TCPServer.no_engines_listening_address_list,
                engines_list=config_static.ENGINES_LIST
            )
        except socket_wrapper.SocketWrapperPortInUseError as e:
            print_api.print_api(e, error_type=True, color="red", logger=system_logger)
            # Wait for the message to be printed and saved to file.
            time.sleep(1)
            network_logger_queue_listener.stop()
            return 1
        except socket_wrapper.SocketWrapperConfigurationValuesError as e:
            print_api.print_api(e, error_type=True, color="red", logger=system_logger, logger_method='critical')
            # Wait for the message to be printed and saved to file.
            time.sleep(1)
            network_logger_queue_listener.stop()
            return 1

        # ----------------------- Get the default network adapter configuration. --------------------------
        # This setting is needed only for the dns gateways configurations from the main config on localhost.
        set_local_dns_gateway: bool = False
        # Set the default gateway if specified.
        if config_static.DNSServer.set_default_dns_gateway:
            dns_gateway_server_list = config_static.DNSServer.set_default_dns_gateway
            set_local_dns_gateway = True
        elif config_static.DNSServer.set_default_dns_gateway_to_localhost:
            dns_gateway_server_list = [base.LOCALHOST_IPV4]
            set_local_dns_gateway = True
        elif config_static.DNSServer.set_default_dns_gateway_to_default_interface_ipv4:
            dns_gateway_server_list = [base.DEFAULT_IPV4]
            set_local_dns_gateway = True
        else:
            dns_gateway_server_list = NETWORK_INTERFACE_SETTINGS.dns_gateways

        if config_static.ENGINES_LIST[0].is_localhost:
            if set_local_dns_gateway:
                global IS_SET_DNS_GATEWAY
                IS_SET_DNS_GATEWAY = True

                # Get current network interface state.
                global NETWORK_INTERFACE_IS_DYNAMIC, NETWORK_INTERFACE_IPV4_ADDRESS_LIST
                NETWORK_INTERFACE_IS_DYNAMIC, NETWORK_INTERFACE_IPV4_ADDRESS_LIST = dns.get_default_dns_gateway()

                # Set the DNS gateway to the specified one only if the DNS gateway is dynamic, or it is static but different
                # from the one specified in the configuration file.
                if (NETWORK_INTERFACE_IS_DYNAMIC or (not NETWORK_INTERFACE_IS_DYNAMIC and
                                                     NETWORK_INTERFACE_IPV4_ADDRESS_LIST != dns_gateway_server_list)):
                    try:
                        dns.set_connection_dns_gateway_static(
                            dns_servers=dns_gateway_server_list,
                            use_default_connection=True
                        )
                    except PermissionError as e:
                        print_api.print_api(e, error_type=True, color="red", logger=system_logger)
                        # Wait for the message to be printed and saved to file.
                        time.sleep(1)
                        network_logger_queue_listener.stop()
                        return 1
        else:
            # Change the adapter settings and add the virtual IPs.
            try:
                networks.add_virtual_ips_to_default_adapter_by_current_setting(
                    virtual_ipv4s_to_add=IPS_TO_ASSIGN, virtual_ipv4_masks_to_add=MASKS_TO_ASSIGN, dns_gateways=dns_gateway_server_list)
            except PermissionError as e:
                print_api.print_api(e, error_type=True, color="red", logger=system_logger)
                # Wait for the message to be printed and saved to file.
                time.sleep(1)
                network_logger_queue_listener.stop()
                return 1

        statistics_writer = socket_wrapper_instance.statistics_writer

        socket_wrapper_instance.start_listening_sockets(
            reference_function_name=thread_worker_main,
            reference_function_args=(
                network_logger_with_queue_handler, statistics_writer, config_static.ENGINES_LIST,
                config_static.REFERENCE_MODULE)
        )

        # socket_thread = threading.Thread(
        #     target=socket_wrapper_instance.loop_for_incoming_sockets,
        #     kwargs={
        #         'reference_function_name': thread_worker_main,
        #         'reference_function_args': (network_logger_with_queue_handler, statistics_writer, engines_list, reference_module,)
        #     },
        #     name="accepting_loop"
        # )
        #
        # socket_thread.daemon = True
        # socket_thread.start()

        # Compress recordings each day in a separate process.
        recs_archiver_thread = threading.Thread(target=_loop_at_midnight_recs_archive, args=(network_logger_name,), daemon=True)
        recs_archiver_thread.start()

    if config_static.DNSServer.enable or config_static.TCPServer.enable:
        # This is needed for Keyboard Exception.
        while True:
            time.sleep(1)


def _loop_at_midnight_recs_archive(network_logger_name):
    previous_date = datetime.datetime.now().strftime('%d')
    while True:
        # Get current time.
        current_date = datetime.datetime.now().strftime('%d')
        # If it's midnight, start the archiving process.
        if current_date != previous_date:
            if config_static.LogRec.enable_request_response_recordings_in_logs:
                global RECS_PROCESS_INSTANCE
                RECS_PROCESS_INSTANCE = recs_files.recs_archiver_in_process(
                    config_static.LogRec.recordings_path,
                    logging_queue=NETWORK_LOGGER_QUEUE,
                    logger_name=network_logger_name,
                    finalize_output_queue=FINALIZE_RECS_ARCHIVE_QUEUE
                )

                archiver_result = FINALIZE_RECS_ARCHIVE_QUEUE.get()
                if isinstance(archiver_result, Exception):
                    MITM_ERROR_LOGGER.write(archiver_result)

            # Update the previous date.
            previous_date = current_date
        # Sleep for 1 minute.
        time.sleep(60)


def mitm_server_main(config_file_path: str, script_version: str):
    try:
        # Main function should return integer with error code, 0 is successful.
        return mitm_server(config_file_path, script_version)
    except KeyboardInterrupt:
        print_api.print_api("Server Stopped by [KeyboardInterrupt].", color='blue')
        exit_cleanup()
        return 0
    except Exception as e:
        print_api.print_api('', error_type=True, color='red', traceback_string=True)
        # The error logger will not be initiated if there will be a problem with configuration file or checks.
        if MITM_ERROR_LOGGER is not None:
            MITM_ERROR_LOGGER.write(e)
        exit_cleanup()
        return 1

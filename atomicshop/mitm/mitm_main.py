import threading
import multiprocessing
import time
import datetime
import os
import sys
import logging
import signal

import atomicshop   # Importing atomicshop package to get the version of the package.

from .. import filesystem, on_exit, print_api, networks, dns
from ..permissions import permissions
from ..python_functions import get_current_python_version_string, check_python_version_compliance
from ..wrappers.socketw import socket_wrapper, dns_server, base, statistics_csv
from ..wrappers.loggingw import loggingw
from ..wrappers.ctyping import win_console
from ..basics import multiprocesses

from .connection_thread_worker import thread_worker_main
from . import config_static, recs_files


# If you have 'pip-system-certs' package installed, this section overrides this behavior, since it injects
# the ssl default behavior, which we don't need when using ssl and sockets.
import ssl, importlib
if getattr(ssl.SSLContext.wrap_socket, "__module__", "").startswith("pip._vendor.truststore"):
    # Truststore injection is active; restore stdlib ssl
    importlib.reload(ssl)


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


STATISTICS_LOGGER_NAME: str = 'statistics'
EXCEPTIONS_CSV_LOGGER_NAME: str = 'exceptions'
EXCEPTIONS_CSV_LOGGER_HEADER: str = 'time,exception'
# noinspection PyTypeChecker
MITM_ERROR_LOGGER: loggingw.ExceptionCsvLogger = None

# Create logger queues.
NETWORK_LOGGER_QUEUE: multiprocessing.Queue = multiprocessing.Queue()
STATISTICS_CSV_LOGGER_QUEUE: multiprocessing.Queue = multiprocessing.Queue()
EXCEPTIONS_CSV_LOGGER_QUEUE: multiprocessing.Queue = multiprocessing.Queue()

# Create finalization queue for the rec archiving process.
FINALIZE_RECS_ARCHIVE_QUEUE: multiprocessing.Queue = multiprocessing.Queue()


try:
    win_console.disable_quick_edit()
except win_console.NotWindowsConsoleError:
    pass


def _graceful_shutdown(signum, frame):
    exit_cleanup()


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

    if config_static.Certificates.sni_create_server_certificate_for_each_domain:
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
    result = config_static.load_config(config_file_path, print_kwargs=dict(stdout=False))
    if result != 0:
        return result

    # Get the IPs that will be set for the adapter and fill the engine configuration with the IPs.
    get_ipv4s_for_tcp_server()

    global MITM_ERROR_LOGGER
    MITM_ERROR_LOGGER = loggingw.ExceptionCsvLogger(
        logger_name=EXCEPTIONS_CSV_LOGGER_NAME,
        directory_path=config_static.LogRec.logs_path,
        log_queue=EXCEPTIONS_CSV_LOGGER_QUEUE,
        add_queue_handler_start_listener_multiprocessing=True,
    )

    # Create folders.
    filesystem.create_directory(config_static.LogRec.logs_path)

    if config_static.Certificates.sni_get_server_certificate_from_server_socket:
        filesystem.create_directory(
            config_static.Certificates.sni_server_certificate_from_server_socket_download_directory)

    network_logger_name = config_static.MainConfig.LOGGER_NAME

    # Start the network logger and its queue listener.
    _ = loggingw.create_logger(
        logger_name=network_logger_name,
        log_queue=NETWORK_LOGGER_QUEUE,
        start_queue_listener_multiprocess_add_queue_handler=True,
        file_path=f'{config_static.LogRec.logs_path}{os.sep}{network_logger_name}.txt',
        add_stream=True,
        add_timedfile=True,
        formatter_streamhandler='DEFAULT',
        formatter_filehandler='DEFAULT',
        backupCount=config_static.LogRec.store_logs_for_x_days)

    """
    # Create this in other multiprocesses (You need to pass only the logger_name and log_queue to the other process):
    logger = loggingw.create_logger(
        logger_name=logger_name,
        add_queue_handler=True,
        log_queue=NETWORK_LOGGER_QUEUE
    )
    """

    # Initiate Listener logger, which is a child of network logger, so he uses the same settings and handlers
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
            # network_logger_queue_listener.stop()
            return 1

    # Logging Startup information.
    startup_output(system_logger, script_version)

    multiprocess_list: list[multiprocessing.Process] = list()
    # noinspection PyTypeHints
    is_ready_multiprocessing_event_list: list[multiprocessing.Event] = list()

    # === Initialize TCP Server ====================================================================================
    if config_static.TCPServer.enable:
        # Get the default network adapter configuration and set the one from config.
        # We set the virtual IPs in the network adapter here, so the server multiprocessing processes can listen on them.
        setting_result: int = _add_virtual_ips_set_default_dns_gateway(system_logger)
        if setting_result != 0:
            print_api.print_api("Failed to set the default DNS gateway OR Virtual IPs.", error_type=True, color="red",
                                logger=system_logger)
            # Wait for the message to be printed and saved to file.
            time.sleep(1)
            return setting_result

        # Start statistics CSV Queue listener and the logger.
        _ = statistics_csv.StatisticsCSVWriter(
            directory_path=config_static.LogRec.logs_path,
            log_queue=STATISTICS_CSV_LOGGER_QUEUE,
            add_queue_handler_start_listener_multiprocessing=True)

        no_engine_usage_enable: bool = config_static.TCPServer.no_engines_usage_to_listen_addresses_enable
        no_engines_listening_address_list: list[str] = config_static.TCPServer.no_engines_listening_address_list

        # If engines were passed, we will use the listening addresses from the engines.
        listening_interfaces: list[dict] = list()
        if not no_engine_usage_enable:
            for engine in config_static.ENGINES_LIST:
                # Combine the domain and port dicts.
                connection_dict: dict = {**engine.domain_target_dict, **engine.port_target_dict}

                # Start all the regular listening interfaces.
                for domain_or_port, ip_port_dict in connection_dict.items():
                    current_interface_dict: dict = {
                        'engine': engine,
                        'process_name': f'tcp_server-{engine.engine_name}-{domain_or_port}',
                        'ip': ip_port_dict['ip'],
                        'port': int(ip_port_dict['port'])
                    }
                    listening_interfaces.append(current_interface_dict)
        else:
            # If no engines were passed, we will use the listening addresses from the configuration.
            for address in no_engines_listening_address_list:
                listening_ip_address, port_str = address.split(':')
                current_interface_dict: dict = {
                    'engine': None,  # No engine for this address.
                    'process_name': f'tcp_server-{listening_ip_address}_{port_str}',
                    'ip': listening_ip_address,
                    'port': int(port_str)
                }
                listening_interfaces.append(current_interface_dict)

        # Starting the TCP server multiprocessing processes.
        for interface_dict in listening_interfaces:
            socket_wrapper_kwargs: dict = dict(
                ip_address=interface_dict['ip'],
                port=interface_dict['port'],
                engine=interface_dict['engine'],
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
                logs_directory=config_static.LogRec.logs_path,
                logger_name=network_logger_name,
                logger_queue=NETWORK_LOGGER_QUEUE,
                statistics_logger_name=STATISTICS_LOGGER_NAME,
                statistics_logger_queue=STATISTICS_CSV_LOGGER_QUEUE,
                exceptions_logger_name=EXCEPTIONS_CSV_LOGGER_NAME,
                exceptions_logger_queue=EXCEPTIONS_CSV_LOGGER_QUEUE,
                forwarding_dns_service_ipv4_list___only_for_localhost=[config_static.DNSServer.forwarding_dns_service_ipv4],
                skip_extension_id_list=config_static.SkipExtensions.SKIP_EXTENSION_ID_LIST,
                print_kwargs=dict(stdout=False)
            )

            # noinspection PyTypeHints
            is_tcp_process_ready: multiprocessing.Event = multiprocessing.Event()
            is_ready_multiprocessing_event_list.append(is_tcp_process_ready)

            tcp_process: multiprocessing.Process = multiprocessing.Process(
                target=_create_tcp_server_process,
                name=interface_dict['process_name'],
                args=(
                    socket_wrapper_kwargs,
                    config_file_path,
                    network_logger_name,
                    NETWORK_LOGGER_QUEUE,
                    is_tcp_process_ready
                ),
                daemon=True
            )
            tcp_process.start()
            multiprocess_list.append(tcp_process)

        # Compress recordings each day in a separate process.
        recs_archiver_thread = threading.Thread(target=_loop_at_midnight_recs_archive, args=(network_logger_name,), daemon=True)
        recs_archiver_thread.start()

        # Check that all the multiprocesses are ready.
        if not _wait_for_events(is_ready_multiprocessing_event_list, timeout=30, system_logger=system_logger):
            return 1
    # === EOF Initialize TCP Server ====================================================================================

    # === Initialize DNS module ========================================================================================
    if config_static.DNSServer.enable:
        # noinspection PyTypeHints
        is_dns_process_ready: multiprocessing.Event = multiprocessing.Event()

        dns_server_kwargs: dict = dict(
            listening_address=config_static.DNSServer.listening_address,
            log_directory_path=config_static.LogRec.logs_path,
            backupCount_log_files_x_days=config_static.LogRec.store_logs_for_x_days,
            forwarding_dns_service_ipv4=config_static.DNSServer.forwarding_dns_service_ipv4,
            forwarding_dns_service_port=config_static.DNSServer.forwarding_dns_service_port,
            resolve_by_engine=(
                config_static.DNSServer.resolve_by_engine, config_static.ENGINES_LIST),
            resolve_regular_pass_thru=config_static.DNSServer.resolve_regular_pass_thru,
            resolve_all_domains_to_ipv4=(
                config_static.DNSServer.resolve_all_domains_to_ipv4_enable, config_static.DNSServer.target_ipv4),
            offline_mode=config_static.MainConfig.offline,
            cache_timeout_minutes=config_static.DNSServer.cache_timeout_minutes,
            logging_queue=NETWORK_LOGGER_QUEUE,
            logger_name=network_logger_name,
            is_ready_multiprocessing=is_dns_process_ready
        )

        dns_process = multiprocessing.Process(
            target=dns_server.start_dns_server_multiprocessing_worker,
            kwargs=dns_server_kwargs,
            name="dns_server",
            daemon=True
        )
        dns_process.start()

        multiprocess_list.append(dns_process)

        # Check that the multiprocess is ready.
        if not _wait_for_events([is_dns_process_ready], timeout=30, system_logger=system_logger):
            return 1
    # === EOF Initialize DNS module ====================================================================================

    if config_static.DNSServer.enable or config_static.TCPServer.enable:
        print_api.print_api("The Server is Ready for Operation!", color="green", logger=system_logger)
        print_api.print_api("Press [Ctrl]+[C] to stop.", color='blue', logger=system_logger)

        # Get al the queue listener processes (basically this is not necessary, since they're 'daemons', but this is a good practice).
        multiprocess_list.extend(loggingw.get_listener_processes())

        # This is needed for Keyboard Exception.
        while True:
            # If it is the first cycle and some process had an exception, we will exist before printing that the
            # server is ready for operation.
            result, process_name = multiprocesses.is_process_crashed(multiprocess_list)
            # If result is None, all processes are still alive.
            if result is not None:
                # If result is 0 or 1, we can exit the loop.
                print(f"Process [{process_name}] finished with exit code {result}.")
                break

            time.sleep(1)


# noinspection PyTypeHints
def _create_tcp_server_process(
        socket_wrapper_kwargs: dict,
        config_file_path: str,
        network_logger_name: str,
        network_logger_queue: multiprocessing.Queue,
        is_tcp_process_ready: multiprocessing.Event
):
    # Load config_static per process, since it is not shared between processes.
    config_static.load_config(config_file_path, print_kwargs=dict(stdout=False))

    # First create a network logger with a queue handler.
    _ = loggingw.create_logger(
        logger_name=network_logger_name,
        add_queue_handler=True,
        log_queue=network_logger_queue,
    )

    # Now get the system logger and listener loggers.
    system_logger: logging.Logger = loggingw.get_logger_with_level(f'{network_logger_name}.system')
    # If the listener logger is available in current process, the SocketWrapper will use it.
    _ = loggingw.get_logger_with_level(f'{network_logger_name}.listener')

    try:
        # noinspection PyTypeChecker
        socket_wrapper_instance = socket_wrapper.SocketWrapper(**socket_wrapper_kwargs)
    except socket_wrapper.SocketWrapperPortInUseError as e:
        print_api.print_api(e, error_type=True, color="red", logger=system_logger)
        # Wait for the message to be printed and saved to file.
        time.sleep(1)
        # network_logger_queue_listener.stop()
        sys.exit(1)
    except socket_wrapper.SocketWrapperConfigurationValuesError as e:
        print_api.print_api(e, error_type=True, color="red", logger=system_logger, logger_method='critical')
        # Wait for the message to be printed and saved to file.
        time.sleep(1)
        # network_logger_queue_listener.stop()
        sys.exit(1)

    try:
        socket_wrapper_instance.start_listening_socket(
            callable_function=thread_worker_main, callable_args=(config_static,))
    except OSError as e:
        if e.winerror == 10022:  # Invalid argument error on Windows.
            message = (
                str(f"{e}\n"
                    f"Check that the IP address and port are correct: {socket_wrapper_kwargs['ip_address']}:{socket_wrapper_kwargs['port']}\n"))
            print_api.print_api(message, error_type=True, color="red", logger=system_logger, logger_method='critical')
            # Wait for the message to be printed and saved to file.
            time.sleep(1)
            # network_logger_queue_listener.stop()
            sys.exit(1)
        else:
            raise e

    # Notify that the TCP server is ready.
    is_tcp_process_ready.set()

    try:
        while True:
            time.sleep(1)  # Keep the process alive, since the listening socket is in an infinite loop.
    except KeyboardInterrupt:
        sys.exit(0)


# noinspection PyTypeHints
def _wait_for_events(
        events: list[multiprocessing.Event],
        timeout: int = 30,
        system_logger: logging.Logger = None
) -> bool:
    """
    Wait for all events in the list to be set.

    :param events: List of multiprocessing.Event objects.
    :param timeout: Maximum time to wait for all events to be set.
    :return: True if all events are set, False if timeout occurs.
    """

    # Check that all the multiprocesses are ready.
    for event in events:
        if not event.wait(timeout=timeout):
            print_api.print_api("One of the processes didn't start in time.", error_type=True, color="red",
                                logger=system_logger)
            # Wait for the message to be printed and saved to file.
            time.sleep(1)
            return False

    return True


def _add_virtual_ips_set_default_dns_gateway(system_logger: logging.Logger) -> int:
    """
    The function reads the current DNS gateway setting and sets the new one.

    :param system_logger: The logger to use for logging messages.
    :return: 0 if successful, 1 if there was an error.
    """

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
                    # network_logger_queue_listener.stop()
                    return 1
    else:
        # Change the adapter settings and add the virtual IPs.
        try:
            networks.add_virtual_ips_to_default_adapter_by_current_setting(
                virtual_ipv4s_to_add=IPS_TO_ASSIGN, virtual_ipv4_masks_to_add=MASKS_TO_ASSIGN,
                dns_gateways=dns_gateway_server_list)
        except (PermissionError, TimeoutError) as e:
            print_api.print_api(e, error_type=True, color="red", logger=system_logger)
            # Wait for the message to be printed and saved to file.
            time.sleep(1)
            # network_logger_queue_listener.stop()
            return 1

    return 0


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
    # This is for Linux and MacOS.
    signal.signal(signal.SIGTERM, _graceful_shutdown)
    signal.signal(signal.SIGINT, _graceful_shutdown)
    # This is for Windows.
    """
    Example:
    script = (Path(__file__).resolve().parent / "ServerTCPWithDNS.py").resolve()
    p = subprocess.Popen(
        [sys.executable, "-u", str(script)],
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        # inherit console; do NOT use CREATE_NEW_CONSOLE
    )
    time.sleep(30)
    p.send_signal(signal.CTRL_BREAK_EVENT)
    try:
        p.wait(timeout=5)
    except subprocess.TimeoutExpired:
        print("Graceful interrupt timed out; terminating")
        p.terminate()
        p.wait()
    """
    signal.signal(signal.SIGBREAK, _graceful_shutdown)

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

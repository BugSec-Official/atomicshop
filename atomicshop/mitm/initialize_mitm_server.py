import os
import threading
import time
import datetime

import atomicshop   # Importing atomicshop package to get the version of the package.

from .. import filesystem, queues, dns, on_exit
from ..permissions import permissions
from ..python_functions import get_current_python_version_string, check_python_version_compliance
from ..wrappers.socketw import socket_wrapper, dns_server, base
from ..wrappers.loggingw import loggingw
from ..print_api import print_api

from .initialize_engines import ModuleCategory
from .connection_thread_worker import thread_worker_main
from . import config_static, recs_files


def exit_cleanup():
    if config_static.DNSServer.set_default_dns_gateway:
        is_dns_dynamic, current_dns_gateway = dns.get_default_dns_gateway()
        print_api(f'Current DNS Gateway: {current_dns_gateway}')

        if current_dns_gateway == config_static.DNSServer.set_default_dns_gateway and not is_dns_dynamic:
            if permissions.is_admin():
                dns.set_connection_dns_gateway_dynamic(use_default_connection=True)
                print_api("Returned default DNS gateway...", color='blue')


def initialize_mitm_server(config_file_path: str):
    on_exit.register_exit_handler(exit_cleanup)

    # Main function should return integer with error code, 0 is successful.
    # Since listening server is infinite, this will not be reached.
    # After modules import - we check for python version.
    check_python_version_compliance(minimum_version='3.12')

    # Import the configuration file.
    result = config_static.load_config(config_file_path)
    if result != 0:
        return result

    # Create folders.
    filesystem.create_directory(config_static.Log.logs_path)
    filesystem.create_directory(config_static.Recorder.recordings_path)
    if config_static.Certificates.sni_get_server_certificate_from_server_socket:
        filesystem.create_directory(
            config_static.Certificates.sni_server_certificate_from_server_socket_download_directory)

    # Compress recordings of the previous days if there are any.
    recs_files.recs_archiver_in_process(config_static.Recorder.recordings_path)

    # Create a logger that will log messages to file, Initiate System logger.
    logger_name = "system"
    system_logger = loggingw.create_logger(
        logger_name=logger_name,
        file_path=f"{config_static.Log.logs_path}{os.sep}{logger_name}.txt",
        add_stream=True,
        add_timedfile=True,
        formatter_streamhandler='DEFAULT',
        formatter_filehandler='DEFAULT'
    )

    # Writing first log.
    system_logger.info("======================================")
    system_logger.info("Server Started.")
    system_logger.info(f"Python Version: {get_current_python_version_string()}")
    system_logger.info(f"Script Version: {config_static.SCRIPT_VERSION}")
    system_logger.info(f"Atomic Workshop Version: {atomicshop.__version__}")
    system_logger.info(f"Log folder: {config_static.Log.logs_path}")
    system_logger.info(f"Recordings folder for Requests/Responses: {config_static.Recorder.recordings_path}")
    system_logger.info(f"Loaded system logger: {system_logger}")

    system_logger.info(f"TCP Server Target IP: {config_static.DNSServer.target_tcp_server_ipv4}")

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

    # === Importing engine modules =================================================================================
    system_logger.info("Importing engine modules.")

    # Get full paths of all the 'engine_config.ini' files.
    engine_config_path_list = filesystem.get_file_paths_from_directory(
        directory_path=config_static.MainConfig.ENGINES_DIRECTORY_PATH,
        file_name_check_pattern=config_static.MainConfig.ENGINE_CONFIG_FILE_NAME)

    # Iterate through all the 'engine_config.ini' file paths.
    domains_engine_list_full: list = list()
    engines_list: list = list()
    for engine_config_path in engine_config_path_list:
        # Initialize engine.
        current_module = ModuleCategory(config_static.MainConfig.SCRIPT_DIRECTORY)
        current_module.fill_engine_fields_from_config(engine_config_path)
        current_module.initialize_engine(logs_path=config_static.Log.logs_path,
                                         logger=system_logger)

        # Extending the full engine domain list with this list.
        domains_engine_list_full.extend(current_module.domain_list)
        # Append the object to the engines list
        engines_list.append(current_module)
    # === EOF Importing engine modules =============================================================================
    # ==== Initialize Reference Module =============================================================================
    reference_module = ModuleCategory(config_static.MainConfig.SCRIPT_DIRECTORY)
    reference_module.fill_engine_fields_from_general_reference(config_static.MainConfig.ENGINES_DIRECTORY_PATH)
    reference_module.initialize_engine(logs_path=config_static.Log.logs_path,
                                       logger=system_logger, stdout=False, reference_general=True)
    # === EOF Initialize Reference Module ==========================================================================
    # === Engine logging ===========================================================================================
    # Printing the parsers using "start=1" for index to start counting from "1" and not "0"
    print_api(f"[*] Found Engines:", logger=system_logger)
    for index, engine in enumerate(engines_list, start=1):
        message = f"[*] {index}: {engine.engine_name} | {engine.domain_list}"
        print_api(message, logger=system_logger)

        message = (f"[*] Modules: {engine.parser_class_object.__name__}, "
                   f"{engine.responder_class_object.__name__}, "
                   f"{engine.recorder_class_object.__name__}")
        print_api(message, logger=system_logger)

    if config_static.DNSServer.enable:
        print_api("DNS Server is enabled.", logger=system_logger)

        # If engines were found and dns is set to route by the engine domains.
        if engines_list and config_static.DNSServer.resolve_to_tcp_server_only_engine_domains:
            print_api("Engine domains will be routed by the DNS server to Built-in TCP Server.", logger=system_logger)
        # If engines were found, but the dns isn't set to route to engines.
        elif engines_list and not config_static.DNSServer.resolve_to_tcp_server_only_engine_domains:
            message = f"[*] Engine domains found, but the DNS routing is set not to use them for routing."
            print_api(message, color="yellow", logger=system_logger)
        elif not engines_list and config_static.DNSServer.resolve_to_tcp_server_only_engine_domains:
            raise ValueError("No engines were found, but the DNS routing is set to use them for routing.\n"
                             "Please check your DNS configuration in the 'config.ini' file.")

        if config_static.DNSServer.resolve_to_tcp_server_all_domains:
            print_api("All domains will be routed by the DNS server to Built-in TCP Server.", logger=system_logger)

        if config_static.DNSServer.resolve_regular:
            print_api(
                "Regular DNS resolving is enabled. Built-in TCP server will not be routed to",
                logger=system_logger, color="yellow")
    else:
        print_api("DNS Server is disabled.", logger=system_logger, color="yellow")

    if config_static.TCPServer.enable:
        print_api("TCP Server is enabled.", logger=system_logger)

        if engines_list and not config_static.TCPServer.engines_usage:
            message = \
                f"Engines found, but the TCP server is set not to use them for processing. General responses only."
            print_api(message, color="yellow", logger=system_logger)
        elif engines_list and config_static.TCPServer.engines_usage:
            message = f"Engines found, and the TCP server is set to use them for processing."
            print_api(message, logger=system_logger)
        elif not engines_list and config_static.TCPServer.engines_usage:
            raise ValueError("No engines were found, but the TCP server is set to use them for processing.\n"
                             "Please check your TCP configuration in the 'config.ini' file.")
    else:
        print_api("TCP Server is disabled.", logger=system_logger, color="yellow")

    # === EOF Engine Logging =======================================================================================

    # Assigning all the engines domains to all time domains, that will be responsible for adding new domains.
    config_static.Certificates.domains_all_times = list(domains_engine_list_full)

    network_logger_name = "network"
    network_logger = loggingw.create_logger(
        logger_name=network_logger_name,
        directory_path=config_static.Log.logs_path,
        add_stream=True,
        add_timedfile=True,
        formatter_streamhandler='DEFAULT',
        formatter_filehandler='DEFAULT'
    )
    system_logger.info(f"Loaded network logger: {network_logger}")

    # Initiate Listener logger, which is a child of network logger, so he uses the same settings and handlers
    listener_logger = loggingw.get_logger_with_level(f'{network_logger_name}.listener')
    system_logger.info(f"Loaded listener logger: {listener_logger}")

    print_api("Press [Ctrl]+[C] to stop.", color='blue')

    # Create request domain queue.
    domain_queue = queues.NonBlockQueue()

    # === Initialize DNS module ====================================================================================
    if config_static.DNSServer.enable:
        try:
            dns_server_instance = dns_server.DnsServer(
                listening_interface=config_static.DNSServer.listening_interface,
                listening_port=config_static.DNSServer.listening_port,
                forwarding_dns_service_ipv4=config_static.DNSServer.forwarding_dns_service_ipv4,
                tcp_target_server_ipv4=config_static.DNSServer.target_tcp_server_ipv4,
                # Passing the engine domain list to DNS server to work with.
                # 'list' function re-initializes the current list, or else it will be the same instance object.
                tcp_resolve_domain_list=list(config_static.Certificates.domains_all_times),
                log_directory_path=config_static.Log.logs_path,
                offline_mode=config_static.DNSServer.offline_mode,
                resolve_to_tcp_server_only_tcp_resolve_domains=(
                    config_static.DNSServer.resolve_to_tcp_server_only_engine_domains),
                resolve_to_tcp_server_all_domains=config_static.DNSServer.resolve_to_tcp_server_all_domains,
                resolve_regular=config_static.DNSServer.resolve_regular,
                cache_timeout_minutes=config_static.DNSServer.cache_timeout_minutes,
                request_domain_queue=domain_queue
            )
        except (dns_server.DnsPortInUseError, dns_server.DnsConfigurationValuesError) as e:
            print_api(e, error_type=True, color="red", logger=system_logger)
            # Wait for the message to be printed and saved to file.
            time.sleep(1)
            return 1

        dns_thread = threading.Thread(target=dns_server_instance.start)
        dns_thread.daemon = True
        dns_thread.start()

    # === EOF Initialize DNS module ================================================================================
    # === Initialize TCP Server ====================================================================================
    if config_static.TCPServer.enable:
        try:
            socket_wrapper_instance = socket_wrapper.SocketWrapper(
                listening_interface=config_static.TCPServer.listening_interface,
                listening_port_list=config_static.TCPServer.listening_port_list,
                ca_certificate_name=config_static.MainConfig.ca_certificate_name,
                ca_certificate_filepath=config_static.MainConfig.ca_certificate_filepath,
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
                statistics_logs_directory=config_static.Log.logs_path,
                forwarding_dns_service_ipv4_list___only_for_localhost=(
                    config_static.TCPServer.forwarding_dns_service_ipv4_list___only_for_localhost),
                skip_extension_id_list=config_static.SkipExtensions.SKIP_EXTENSION_ID_LIST,
                request_domain_from_dns_server_queue=domain_queue
            )
        except socket_wrapper.SocketWrapperPortInUseError as e:
            print_api(e, error_type=True, color="red", logger=system_logger)
            # Wait for the message to be printed and saved to file.
            time.sleep(1)
            return 1

        statistics_writer = socket_wrapper_instance.statistics_writer

        socket_wrapper_instance.create_tcp_listening_socket_list()

        # Before we start the loop. we can set the default gateway if specified.
        set_dns_gateway = False
        dns_gateway_server_list = list()
        if config_static.DNSServer.set_default_dns_gateway:
            dns_gateway_server_list = config_static.DNSServer.set_default_dns_gateway
            set_dns_gateway = True
        elif config_static.DNSServer.set_default_dns_gateway_to_localhost:
            dns_gateway_server_list = [base.LOCALHOST_IPV4]
            set_dns_gateway = True
        elif config_static.DNSServer.set_default_dns_gateway_to_default_interface_ipv4:
            dns_gateway_server_list = [base.DEFAULT_IPV4]
            set_dns_gateway = True

        if set_dns_gateway:
            # noinspection PyTypeChecker
            dns.set_connection_dns_gateway_static(
                dns_servers=dns_gateway_server_list,
                use_default_connection=True
            )

        # General exception handler will catch all the exceptions that occurred in the threads and write it to the log.
        # noinspection PyBroadException
        try:
            socket_thread = threading.Thread(
                target=socket_wrapper_instance.loop_for_incoming_sockets,
                kwargs={
                    'reference_function_name': thread_worker_main,
                    'reference_function_args': (network_logger, statistics_writer, engines_list, reference_module,)
                }
            )

            socket_thread.daemon = True
            socket_thread.start()
        except Exception:
            message = f"Unhandled Exception occurred in 'loop_for_incoming_sockets' function"
            print_api(message, error_type=True, color="red", logger=network_logger, traceback_string=True, oneline=True)

        # Compress recordings each day in a separate process.
        recs_archiver_thread = threading.Thread(target=_loop_at_midnight_recs_archive)
        recs_archiver_thread.daemon = True
        recs_archiver_thread.start()

        # This is needed for Keyboard Exception.
        while True:
            time.sleep(1)


def _loop_at_midnight_recs_archive():
    previous_date = datetime.datetime.now().strftime('%d')
    while True:
        # Get current time.
        current_date = datetime.datetime.now().strftime('%d')
        # If it's midnight, start the archiving process.
        if current_date != previous_date:
            recs_files.recs_archiver_in_process(config_static.Recorder.recordings_path)
            # Update the previous date.
            previous_date = current_date
        # Sleep for 1 minute.
        time.sleep(60)

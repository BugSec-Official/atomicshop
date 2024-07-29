import os
import sys
import threading
import time

# Importing atomicshop package to get the version of the package.
import atomicshop

from .import_config import ImportConfig
from .initialize_engines import ModuleCategory
from .connection_thread_worker import thread_worker_main
from .. import filesystem, queues
from ..python_functions import get_current_python_version_string, check_python_version_compliance
from ..wrappers.socketw.socket_wrapper import SocketWrapper
from ..wrappers.socketw import dns_server
from ..wrappers.psutilw import networks
from ..basics import dicts_nested
from ..wrappers.loggingw import loggingw
from ..print_api import print_api


STATISTICS_HEADER: str = \
    'request_time_sent,host,path,command,status_code,request_size_bytes,response_size_bytes,file_path,process_cmd,error'


def initialize_mitm_server(config_static):
    # Main function should return integer with error code, 0 is successful.
    # Since listening server is infinite, this will not be reached.
    # After modules import - we check for python version.
    check_python_version_compliance(minimum_version='3.11')

    # Preparing everything for the logging module.
    # Log folder path is in the "config.ini" file, so we need to read it before setting loggers.
    config_importer = ImportConfig(
        file_name=config_static.CONFIG_INI_SERVER_FILE_NAME, directory_path=config_static.WORKING_DIRECTORY)
    config_importer.open()
    config = config_importer.config

    # Create folders.
    filesystem.create_directory(config['log']['logs_path'])
    filesystem.create_directory(config['recorder']['recordings_path'])
    if config['certificates']['sni_get_server_certificate_from_server_socket']:
        filesystem.create_directory(
            config['certificates']['sni_server_certificate_from_server_socket_download_directory'])

    # Create a logger that will log messages to file, Initiate System logger.
    logger_name = "system"
    system_logger = loggingw.create_logger(
        logger_name=logger_name,
        file_path=f"{config['log']['logs_path']}{os.sep}{logger_name}.txt",
        add_stream=True,
        add_timedfile=True,
        formatter_streamhandler='DEFAULT',
        formatter_filehandler='DEFAULT'
    )

    # Writing first log.
    system_logger.info("======================================")

    if config_importer.admin_rights is not None:
        if not config_importer.admin_rights:
            system_logger.error("User continued with errors on Command Line harvesting for system processes.")

    system_logger.info("Server Started.")
    system_logger.info(f"Python Version: {get_current_python_version_string()}")
    system_logger.info(f"Script Version: {config_static.SCRIPT_VERSION}")
    system_logger.info(f"Atomic Workshop Version: {atomicshop.__version__}")
    system_logger.info(f"Loaded config.ini: {config_importer.config_parser.file_path}")
    system_logger.info(f"Log folder: {config['log']['logs_path']}")
    system_logger.info(f"Recordings folder for Requests/Responses: {config['recorder']['recordings_path']}")
    system_logger.info(f"Loaded system logger: {system_logger}")

    system_logger.info(f"TCP Server Target IP: {config['dns']['target_tcp_server_ipv4']}")

    # Some 'config.ini' settings logging ===========================================================================
    if config['certificates']['default_server_certificate_usage']:
        system_logger.info(
            f"Default server certificate usage enabled, if no SNI available: "
            f"{config_static.CONFIG_EXTENDED['certificates']['default_server_certificate_directory']}"
            f"{os.sep}{config_static.CONFIG_EXTENDED['certificates']['default_server_certificate_name']}.pem")

    if config['certificates']['sni_server_certificates_cache_directory']:
        system_logger.info(
            f"SNI function certificates creation enabled. Certificates cache: "
            f"{config['certificates']['sni_server_certificates_cache_directory']}")
    else:
        system_logger.info(f"SNI function certificates creation disabled.")

    if config['certificates']['custom_server_certificate_usage']:
        system_logger.info(f"Custom server certificate usage is enabled.")
        system_logger.info(f"Custom Certificate Path: {config['certificates']['custom_server_certificate_path']}")

        # If 'custom_private_key_path' field was populated.
        if config['certificates']['custom_private_key_path']:
            system_logger.info(
                f"Custom Certificate Private Key Path: {config['certificates']['custom_private_key_path']}")
        else:
            system_logger.info(f"Custom Certificate Private Key Path wasn't provided in [advanced] section. "
                               f"Assuming the private key is inside the certificate file.")

    # === Importing engine modules =================================================================================
    system_logger.info("Importing engine modules.")

    # Get full paths of all the 'engine_config.ini' files.
    engine_config_path_list = filesystem.get_file_paths_from_directory(
        directory_path=config_static.ENGINES_DIRECTORY_PATH,
        file_name_check_pattern=config_static.ENGINE_CONFIG_FILE_NAME)

    # Iterate through all the 'engine_config.ini' file paths.
    domains_engine_list_full: list = list()
    engines_list: list = list()
    for engine_config_path in engine_config_path_list:
        # Initialize engine.
        current_module = ModuleCategory(config_static.WORKING_DIRECTORY)
        current_module.fill_engine_fields_from_config(engine_config_path)
        current_module.initialize_engine(logs_path=config['log']['logs_path'],
                                         logger=system_logger)

        # Extending the full engine domain list with this list.
        domains_engine_list_full.extend(current_module.domain_list)
        # Append the object to the engines list
        engines_list.append(current_module)
    # === EOF Importing engine modules =============================================================================
    # ==== Initialize Reference Module =============================================================================
    reference_module = ModuleCategory(config_static.WORKING_DIRECTORY)
    reference_module.fill_engine_fields_from_general_reference(config_static.ENGINES_DIRECTORY_PATH)
    reference_module.initialize_engine(logs_path=config['log']['logs_path'],
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

    if config['dns']['enable_dns_server']:
        print_api("DNS Server is enabled.", logger=system_logger)

        # If engines were found and dns is set to route by the engine domains.
        if engines_list and config['dns']['route_to_tcp_server_only_engine_domains']:
            print_api("Engine domains will be routed by the DNS server to Built-in TCP Server.", logger=system_logger)
        # If engines were found, but the dns isn't set to route to engines.
        elif engines_list and not config['dns']['route_to_tcp_server_only_engine_domains']:
            message = f"[*] Engine domains found, but the DNS routing is set not to use them for routing."
            print_api(message, color="yellow", logger=system_logger)
        elif not engines_list and config['dns']['route_to_tcp_server_only_engine_domains']:
            raise ValueError("No engines were found, but the DNS routing is set to use them for routing.\n"
                             "Please check your DNS configuration in the 'config.ini' file.")

        if config['dns']['route_to_tcp_server_all_domains']:
            print_api("All domains will be routed by the DNS server to Built-in TCP Server.", logger=system_logger)

        if config['dns']['regular_resolving']:
            print_api(
                "Regular DNS resolving is enabled. Built-in TCP server will not be routed to",
                logger=system_logger, color="yellow")
    else:
        print_api("DNS Server is disabled.", logger=system_logger, color="yellow")

    if config['tcp']['enable_tcp_server']:
        print_api("TCP Server is enabled.", logger=system_logger)

        if engines_list and not config['tcp']['engines_usage']:
            message = \
                f"Engines found, but the TCP server is set not to use them for processing. General responses only."
            print_api(message, color="yellow", logger=system_logger)
        elif engines_list and config['tcp']['engines_usage']:
            message = f"Engines found, and the TCP server is set to use them for processing."
            print_api(message, logger=system_logger)
        elif not engines_list and config['tcp']['engines_usage']:
            raise ValueError("No engines were found, but the TCP server is set to use them for processing.\n"
                             "Please check your TCP configuration in the 'config.ini' file.")
    else:
        print_api("TCP Server is disabled.", logger=system_logger, color="yellow")

    # === EOF Engine Logging =======================================================================================

    # Assigning all the engines domains to all time domains, that will be responsible for adding new domains.
    config_static.CONFIG_EXTENDED['certificates']['domains_all_times'] = list(domains_engine_list_full)

    # Creating Statistics logger.
    statistics_logger = loggingw.create_logger(
        logger_name="statistics",
        directory_path=config['log']['logs_path'],
        add_timedfile=True,
        formatter_filehandler='MESSAGE',
        file_type='csv',
        header=STATISTICS_HEADER
    )

    network_logger_name = "network"
    network_logger = loggingw.create_logger(
        logger_name=network_logger_name,
        directory_path=config['log']['logs_path'],
        add_stream=True,
        add_timedfile=True,
        formatter_streamhandler='DEFAULT',
        formatter_filehandler='DEFAULT'
    )
    system_logger.info(f"Loaded network logger: {network_logger}")

    # Initiate Listener logger, which is a child of network logger, so he uses the same settings and handlers
    listener_logger = loggingw.get_logger_with_level(f'{network_logger_name}.listener')
    system_logger.info(f"Loaded listener logger: {listener_logger}")

    # Create request domain queue.
    domain_queue = queues.NonBlockQueue()

    # === Initialize DNS module ====================================================================================
    if config['dns']['enable_dns_server']:
        # Check if the DNS server port is in use.
        port_in_use = networks.get_processes_using_port_list([config['dns']['listening_port']])
        if port_in_use:
            for port, process_info in port_in_use.items():
                message = f"Port [{port}] is already in use by process: {process_info}"
                print_api(message, error_type=True, logger_method='critical', logger=system_logger)

            # Wait for the message to be printed and saved to file.
            time.sleep(1)
            sys.exit(1)

        # before executing TCP sockets and after executing 'network' logger.
        dns_server_instance = dns_server.DnsServer(config)
        # Passing the engine domain list to DNS server to work with.
        # 'list' function re-initializes the current list, or else it will be the same instance object.
        dns_server_instance.domain_list = list(domains_engine_list_full)

        dns_server_instance.request_domain_queue = domain_queue
        # Initiate the thread.
        dns_thread = threading.Thread(target=dns_server_instance.start)
        dns_thread.daemon = True
        dns_thread.start()

    # === EOF Initialize DNS module ================================================================================
    # === Initialize TCP Server ====================================================================================
    if config['tcp']['enable_tcp_server']:
        port_in_use = networks.get_processes_using_port_list(config['tcp']['listening_port_list'])
        if port_in_use:
            for port, process_info in port_in_use.items():
                print_api(f"Port [{port}] is already in use by process: {process_info}", logger=system_logger,
                          error_type=True, logger_method='critical')
            # Wait for the message to be printed and saved to file.
            time.sleep(1)
            sys.exit(1)

        socket_wrapper = SocketWrapper(
            config=dicts_nested.merge(config, config_static.CONFIG_EXTENDED), logger=listener_logger,
            statistics_logger=statistics_logger)

        socket_wrapper.create_tcp_listening_socket_list()

        socket_wrapper.requested_domain_from_dns_server = domain_queue

        # General exception handler will catch all the exceptions that occurred in the threads and write it to the log.
        try:
            socket_wrapper.loop_for_incoming_sockets(function_reference=thread_worker_main, reference_args=(
                network_logger, statistics_logger, engines_list, reference_module, config,))
        except Exception:
            message = f"Unhandled Exception occurred in 'loop_for_incoming_sockets' function"
            print_api(message, error_type=True, color="red", logger=network_logger, traceback_string=True, oneline=True)

    # === EOF Initialize TCP Server ================================================================================

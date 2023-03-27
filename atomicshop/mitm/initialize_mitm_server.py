# v1.0.2 - 26.03.2023 18:40
import os
import threading

import atomicshop
from .import_config import ImportConfig
from .initialize_engines import ModuleCategory
from .connection_thread_worker import thread_worker_main
from ..filesystem import get_file_paths_and_relative_directories, ComparisonOperator
from .. import filesystem
from ..python_functions import get_current_python_version_string, check_python_version_compliance
from ..sockets.socket_wrapper import SocketWrapper, DomainQueue
from ..sockets.dns_server import DnsServer
from ..basics import dicts_nested
from ..logger_custom import CustomLogger


def initialize_mitm_server(config_static):
    # Main function should return integer with error code, 0 is successful.
    # Since listening server is infinite, this will not be reached.
    def output_statistics_csv_header():
        # Since there is no implementation of header in logging file handler modules, we'll do it manually each time.
        statistics_header: list = ['request_time_sent',
                                   'host',
                                   'path',
                                   'command',
                                   'status_code',
                                   'request_size_bytes',
                                   'response_size_bytes',
                                   # 'request_hex',
                                   # 'response_hex',
                                   'file_path',
                                   'process_cmd',
                                   'error'
                                   ]
        statistics.logger.info(','.join(statistics_header))

    # After modules import - we check for python version.
    check_python_version_compliance(minimum_version='3.10')

    # Preparing everything for the logging module.
    # Log folder path is in the "config.ini" file, so we need to read it before setting loggers.
    config_importer = ImportConfig(
        file_name=config_static.CONFIG_INI_SERVER_FILE_NAME, directory_path=config_static.WORKING_DIRECTORY)
    config_importer.open()
    config = config_importer.config

    # Create basic folders.
    filesystem.create_folder(config['log']['logs_path'])
    filesystem.create_folder(config['recorder']['recordings_path'])

    # Create a logger that will log messages to file, Initiate System logger.
    system = type('', (), {})()
    system.logger = CustomLogger("system")
    system.logger.add_timedfilehandler_with_queuehandler(config_static.TXT_EXTENSION, config['log']['logs_path'])

    # Writing first log.
    system.logger.info("======================================")

    if config_importer.admin_rights is not None:
        if not config_importer.admin_rights:
            system.logger.error("User continued with errors on Command Line harvesting for system processes.")

    system.logger.info("Server Started.")
    system.logger.info(f"Python Version: {get_current_python_version_string()}")
    system.logger.info(f"Script Version: {config_static.SCRIPT_VERSION}")
    system.logger.info(f"Atomic Workshop Version: {atomicshop.__version__}")
    system.logger.info(f"Loaded config.ini: {config_importer.config_parser.file_path}")
    system.logger.info(f"Log folder: {config['log']['logs_path']}")
    system.logger.info(f"Recordings folder for Requests/Responses: {config['recorder']['recordings_path']}")
    system.logger.info(f"Loaded system logger: {system.logger}")

    # Catching exception on the main execution to log.
    try:
        system.logger.info(f"TCP Server Target IP: {config['dns']['target_tcp_server_ipv4']}")

        # Some 'config.ini' settings logging ===========================================================================
        if config['certificates']['default_server_certificate_usage']:
            system.logger.info(
                f"Default server certificate usage enabled, if no SNI available: "
                f"{config_static.CONFIG_EXTENDED['certificates']['default_server_certificate_directory']}"
                f"{os.sep}{config_static.CONFIG_EXTENDED['certificates']['default_server_certificate_name']}.pem")

        if config['certificates']['sni_create_server_certificate_for_each_domain']:
            system.logger.info(
                f"SNI function certificates creation enabled. Certificates cache: "
                f"{config_static.CONFIG_EXTENDED['certificates']['sni_server_certificates_cache_directory']}")
        else:
            system.logger.info(f"SNI function certificates creation disabled.")

        if config['certificates']['custom_server_certificate_usage']:
            system.logger.info(f"Custom server certificate usage is enabled.")
            system.logger.info(f"Custom Certificate Path: {config['certificates']['custom_server_certificate_path']}")

            # If 'custom_private_key_path' field was populated.
            if config['certificates']['custom_private_key_path']:
                system.logger.info(
                    f"Custom Certificate Private Key Path: {config['certificates']['custom_private_key_path']}")
            else:
                system.logger.info(f"Custom Certificate Private Key Path wasn't provided in [advanced] section. "
                                   f"Assuming the private key is inside the certificate file.")

        # === Importing engine modules =================================================================================
        system.logger.info("Importing engine modules.")

        # Get full paths of all the 'engine_config.ini' files.
        engine_config_path_list, _ = get_file_paths_and_relative_directories(
            directory_fullpath=config_static.ENGINES_DIRECTORY_PATH,
            file_name_check_tuple=(config_static.ENGINE_CONFIG_FILE_NAME, ComparisonOperator.EQ))

        # Iterate through all the 'engine_config.ini' file paths.
        domains_engine_list_full: list = list()
        engines_list: list = list()
        for engine_config_path in engine_config_path_list:
            # Initialize engine.
            current_module = ModuleCategory(config_static.WORKING_DIRECTORY)
            current_module.fill_engine_fields_from_config(engine_config_path)
            current_module.initialize_engine(logs_path=config['log']['logs_path'],
                                             logger=system.logger)

            # Extending the full engine domain list with this list.
            domains_engine_list_full.extend(current_module.domain_list)
            # Append the object to the engines list
            engines_list.append(current_module)
        # === EOF Importing engine modules =============================================================================
        # ==== Initialize Reference Module =============================================================================
        reference_module = ModuleCategory(config_static.WORKING_DIRECTORY)
        reference_module.fill_engine_fields_from_general_reference(config_static.ENGINES_DIRECTORY_PATH)
        reference_module.initialize_engine(logs_path=config['log']['logs_path'],
                                           logger=system.logger, stdout=False, reference_general=True)
        # === EOF Initialize Reference Module ==========================================================================
        # === Engine logging ===========================================================================================
        # If engines were found.
        if engines_list:
            # Printing the parsers using "start=1" for index to start counting from "1" and not "0"
            system.logger.info("[*] Found Engines:")
            for index, engine in enumerate(engines_list, start=1):
                system.logger.info(f"[*] {index}: {engine.engine_name} | {engine.domain_list}")
                system.logger.info(f"[*] Modules: {engine.parser_class_object.__name__}, "
                                   f"{engine.responder_class_object.__name__}, "
                                   f"{engine.recorder_class_object.__name__}")
        # If engines weren't found.
        else:
            system.logger.info("[*] NO ENGINES WERE FOUND!")
            system.logger.info(f"Server will process all the incoming (domains) connections by "
                               f"[{reference_module.engine_name}] engine.")
        # === EOF Engine Logging =======================================================================================

        # Assigning all the engines domains to all time domains, that will be responsible for adding new domains.
        config_static.CONFIG_EXTENDED['certificates']['domains_all_times'] = list(domains_engine_list_full)

        # Creating Statistics logger.
        statistics_logger_name = "statistics"
        statistics = type('', (), {})()
        statistics.logger = CustomLogger(logger_name=statistics_logger_name)
        statistics.logger.add_timedfilehandler_with_queuehandler(
            file_extension=config_static.CSV_EXTENSION,
            directory_path=config['log']['logs_path'],
            formatter='{message}'
        )
        output_statistics_csv_header()

        # Create and initiate empty class, so we can add logger as attribute
        # class Network: pass
        network_logger_name = "network"
        network = type('', (), {})()
        network.logger = CustomLogger(logger_name=network_logger_name)
        network.logger.add_timedfilehandler_with_queuehandler(
            file_extension=config_static.TXT_EXTENSION, directory_path=config['log']['logs_path'])
        network.logger.add_timedfilehandler_with_queuehandler(
            file_extension=config_static.CSV_EXTENSION, directory_path=config['log']['logs_path'])
        system.logger.info(f"Loaded network logger: {network.logger}")

        # Initiate Listener logger, which is a child of network logger, so he uses the same settings and handlers
        listener = type('', (), {})()
        listener.logger = CustomLogger(network_logger_name + ".listener")
        system.logger.info(f"Loaded listener logger: {listener.logger}")

        # Create request domain queue.
        domain_queue = DomainQueue()

        # === Initialize DNS module ====================================================================================
        if config['dns']['enable_dns_server']:
            # before executing TCP sockets and after executing 'network' logger.
            dns_server = DnsServer(config)
            # Passing the engine domain list to DNS server to work with.
            # 'list' function re-initializes the current list, or else it will be the same instance object.
            dns_server.domain_list = list(domains_engine_list_full)

            dns_server.request_domain_queue = domain_queue
            # Initiate the thread.
            threading.Thread(target=dns_server.start).start()
        # === EOF Initialize DNS module ================================================================================

        socket_wrapper = SocketWrapper(
            config=dicts_nested.merge(config, config_static.CONFIG_EXTENDED), logger=listener.logger,
            statistics_logger=statistics.logger)

        socket_wrapper.create_tcp_listening_socket_list()

        socket_wrapper.requested_domain_from_dns_server = domain_queue

        socket_wrapper.loop_for_incoming_sockets(function_reference=thread_worker_main, reference_args=(
            network, statistics, engines_list, reference_module, config,))
    except Exception:
        system.logger.critical_exception("Undocumented exception in General settings of the MAIN thread")
        raise

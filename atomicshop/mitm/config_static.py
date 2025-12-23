import os
from dataclasses import dataclass
from typing import Literal

from . import import_config
from .message import ClientMessage


# noinspection PyTypeChecker
ENGINES_LIST: list = None           # list[initialize_engines.ModuleCategory]
REFERENCE_MODULE = None             # initialize_engines.ModuleCategory


class MainConfig:
    # '' (empty) - system's default internet interface.
    # Any other network interface name available on the system.
    is_offline: bool
    network_interface: str
    is_localhost: bool

    set_default_dns_gateway: list[str]
    set_default_dns_gateway_to_localhost: bool = False
    set_default_dns_gateway_to_network_interface_ipv4: bool = False
    default_localhost_dns_gateway_ipv4: str = '127.0.0.1'

    LOGGER_NAME: str = 'network'

    SCRIPT_DIRECTORY: str = None

    ENGINES_DIRECTORY_PATH: str = None
    ENGINES_DIRECTORY_NAME: str = "engines"
    ENGINE_CONFIG_FILE_NAME: str = "engine_config.toml"

    # Certificates.
    default_server_certificate_name: str = 'default'
    ca_certificate_name: str = 'ElaborateCA'
    ca_certificate_pem_filename: str = f'{ca_certificate_name}.pem'
    ca_certificate_crt_filename: str = f'{ca_certificate_name}_for_manual_installation_not_used_by_script.crt'
    # CA Certificate name and file name without extension.
    ca_certificate_filepath: str = None
    ca_certificate_crt_filepath: str = None
    # Default server certificate file name and path.
    default_server_certificate_filename = f'{default_server_certificate_name}.pem'
    default_server_certificate_filepath: str = None

    @classmethod
    def update(cls):
        # This runs after the dataclass is initialized
        cls.ENGINES_DIRECTORY_PATH = cls.SCRIPT_DIRECTORY + os.sep + cls.ENGINES_DIRECTORY_NAME
        cls.ca_certificate_filepath = f'{cls.SCRIPT_DIRECTORY}{os.sep}{cls.ca_certificate_pem_filename}'
        cls.ca_certificate_crt_filepath = f'{cls.SCRIPT_DIRECTORY}{os.sep}{cls.ca_certificate_crt_filename}'
        cls.default_server_certificate_filepath = \
            f'{cls.SCRIPT_DIRECTORY}{os.sep}{cls.default_server_certificate_filename}'


@dataclass
class DNSServer:
    is_enabled: bool
    offline_mode: bool

    listening_ipv4: str
    listening_port: int

    listening_address: str
    forwarding_dns_service_ipv4: str
    cache_timeout_minutes: int

    resolve_by_engine: bool
    resolve_regular_pass_thru: bool
    resolve_all_domains_to_ipv4_enable: bool
    target_ipv4: str

    # Convertable variables.
    resolve_all_domains_to_ipv4: dict

    # Static variables.
    forwarding_dns_service_port: int = 53



@dataclass
class TCPServer:
    is_enabled: bool
    no_engines_usage_to_listen_addresses_enable: bool
    no_engines_listening_address_list: list[str]

    # Convertable variables.
    no_engines_usage_to_listen_addresses: dict

@dataclass
class LogRec:
    logs_path: str
    recordings_path: str
    enable_request_response_recordings_in_logs: bool
    store_logs_for_x_days: int

    recordings_directory_name: str = 'recs'


@dataclass
class Certificates:
    install_ca_certificate_to_root_store: bool
    uninstall_unused_ca_certificates_with_mitm_ca_name: bool

    default_server_certificate_usage: bool
    sni_add_new_domains_to_default_server_certificate: bool

    custom_server_certificate_usage: bool
    custom_server_certificate_path: str
    custom_private_key_path: str

    sni_create_server_certificate_for_each_domain: bool
    sni_server_certificates_cache_directory: str
    sni_get_server_certificate_from_server_socket: bool
    sni_server_certificate_from_server_socket_download_directory: str

    domains_all_times: list[str]
    sslkeylog_file_path: str

    sslkeylog_file_name: str = "sslkeylog.txt"
    enable_sslkeylogfile_env_to_client_ssl_context: bool = True


@dataclass
class SkipExtensions:
    tls_web_client_authentication: bool
    crl_distribution_points: bool
    authority_information_access: bool

    SKIP_EXTENSION_ID_LIST: list


@dataclass
class ProcessName:
    get_process_name: bool
    ssh_user: str
    ssh_pass: str

    ssh_script_to_execute: Literal['process_from_port', 'process_from_ipv4'] = 'process_from_port'


def load_config(
        config_toml_file_path: str,
        print_kwargs: dict = None
):
    # global CONFIG

    script_path = os.path.dirname(config_toml_file_path)
    MainConfig.SCRIPT_DIRECTORY = script_path
    MainConfig.update()

    # Load the configuration file.
    result = import_config.import_config_files(config_toml_file_path, print_kwargs=print_kwargs or {})
    return result


def get_listening_addresses(client_message: ClientMessage) -> dict | None:
    """
    Get the list of listening addresses from the TCPServer configuration.
    If no_engines_usage_to_listen_addresses_enable is True, return the no_engines_listening_address_list.
    Otherwise, return an empty list.
    """

    for engine in ENGINES_LIST:
        if engine.engine_name == client_message.engine_name:
            return {
                'domain_target_dict': engine.domain_target_dict,
                'port_target_dict': engine.port_target_dict
            }


# ============ Server Tester Specific ===============
CONFIG_INI_TESTER_FILE_NAME: str = 'config_tester.ini'

"""
config.toml:
target_domain_or_ip: the domain or ip that the requests will be sent to. Better use domains, for better testing
    simulation.
target_port: the port that requests will be sent to.
request_type: type of each request: json / string / binary.
    json format that contain a key with hex string of the request that will be converted to bytes.
    string that will contain a request and will be converted to bytes.
    binary file that will contain all request data - will be converted to bytes.
request_json_hex_key_list: this key stores raw request in hex format, since there can be characters that can't be 
    decoded to string / unicode.
    'request_raw_hex' key is the default key in recorded files from mitm server, you may add keys for your custom
     JSON files.
requests_directory: the directory that requests are will be taken from. Can be relative folder that will be in
    current working directory.

parallel_connections_bool: boolean, sets if sockets should be initialized in threads (in parallel) or one after another.
    Use all the connections / cycles in parallel when 'True'. New sockets will be created for each request.
    Reuse the same socket / connection for all the requests when 'False'.
interval_between_requests_defaults_seconds: default interval in seconds between request sends.
interval_between_request_custom_list_seconds: list of intervals in seconds. If this configuration will not be empty,
    this should be a list. Each interval in the list will follow the interval between requests and 
    'interval_between_requests_defaults_seconds' will not be used. It will be used only if number of requests
    is less than then number of intervals in 'interval_between_request_custom_list_seconds'. The missing intervals
    will be filled by default values from 'interval_between_requests_defaults_seconds'.
    Example: you have 10 requests.
        interval_between_requests_defaults_seconds = 5
        interval_between_request_custom_list_seconds = 7, 10, 8, 4, 15
    The rest will be filled from defaults: 7, 10, 8, 4, 15, 5, 5, 5, 5
send_request_batch_cycles: how many batch cycles to send of the same 10 requests (or any other number of requests that
    you might have in the requests folder.
interval_between_batch_cycles_seconds: interval in seconds between each batch.
"""

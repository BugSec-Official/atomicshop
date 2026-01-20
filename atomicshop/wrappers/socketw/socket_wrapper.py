import multiprocessing
import threading
import select
from typing import Literal, Union, Callable, Any
from pathlib import Path
import socket
import shutil
import os

import paramiko

from ...mitm import initialize_engines
from ..psutilw import psutil_networks
from ..certauthw import certauthw
from ..loggingw import loggingw
from ... import package_mains_processor
from ...permissions import permissions
from ... import filesystem, certificates
from ...basics import booleans, tracebacks
from ...print_api import print_api
from ...import ssh_remote

from . import socket_base, creator, process_getter, accepter, statistics_csv, ssl_base, sni


class SocketWrapperPortInUseError(Exception):
    pass


class SocketWrapperConfigurationValuesError(Exception):
    pass


# from ... import queues
# SNI_QUEUE = queues.NonBlockQueue()
LOGS_DIRECTORY_NAME: str = 'logs'


class SocketWrapper:
    def __init__(
            self,
            ip_address: str,
            port: int,
            engine: initialize_engines.ModuleCategory = None,
            forwarding_dns_service_ipv4_list___only_for_localhost: list = None,
            ca_certificate_name: str = None,
            ca_certificate_filepath: str = None,
            ca_certificate_crt_filepath: str = None,
            install_ca_certificate_to_root_store: bool = False,
            uninstall_unused_ca_certificates_with_ca_certificate_name: bool = False,
            default_server_certificate_usage: bool = False,
            default_server_certificate_name: str = None,
            default_certificate_domain_list: list = None,
            default_server_certificate_directory: str = None,
            sni_custom_callback_function: Callable[..., Any] = None,
            sni_use_default_callback_function: bool = False,
            sni_use_default_callback_function_extended: bool = False,
            sni_add_new_domains_to_default_server_certificate: bool = False,
            sni_create_server_certificate_for_each_domain: bool = False,
            sni_server_certificates_cache_directory: str = None,
            sni_get_server_certificate_from_server_socket: bool = False,
            sni_server_certificate_from_server_socket_download_directory: str = None,
            skip_extension_id_list: list = None,
            custom_server_certificate_usage: bool = False,
            custom_server_certificate_path: str = None,
            custom_private_key_path: str = None,
            get_process_name: bool = False,
            ssh_user: str = None,
            ssh_pass: str = None,
            ssh_script_to_execute: Union[
                Literal['process_from_port'],
                None
            ] = None,
            logs_directory: str = None,
            logger_name: str = 'SocketWrapper',
            logger_queue: multiprocessing.Queue = None,
            statistics_logger_name: str = 'statistics',
            statistics_logger_queue: multiprocessing.Queue = None,
            exceptions_logger_name: str = 'SocketWrapperExceptions',
            exceptions_logger_queue: multiprocessing.Queue = None,
            enable_sslkeylogfile_env_to_client_ssl_context: bool = False,
            sslkeylog_file_path: str = None,
            print_kwargs: dict = None,
    ):
        """
        Socket Wrapper class that will be used to create sockets, listen on them, accept connections and send them to
        new threads.

        :param ca_certificate_name: CA certificate name.
        :param ca_certificate_filepath: CA certificate file path with '.pem' extension.
        :param ca_certificate_crt_filepath: CA certificate file path with '.crt' extension.
            This file will be created from the PEM file 'ca_certificate_filepath' for manual installation.
        :param install_ca_certificate_to_root_store: boolean, if True, CA certificate will be installed
            to the root store.
        :param uninstall_unused_ca_certificates_with_ca_certificate_name: boolean, if True, unused CA certificates
            with provided 'ca_certificate_name' will be uninstalled.
        :param default_server_certificate_usage: boolean, if True, default server certificate will be used
            for each incoming socket.
        :param sni_custom_callback_function: callable, custom callback function that will be executed when
            there is a SNI present in the request.

            Example: custom callback function to set the 'server_hostname' for the socket with the domain name from SNI:
                    def sni_handle(
                            sni_ssl_socket: ssl.SSLSocket,
                            sni_destination_name: str,
                            sni_ssl_context: ssl.SSLContext):
                        # Set 'server_hostname' for the socket.
                        sni_ssl_socket.server_hostname = sni_destination_name

                        return sni_handle

            The function should accept 3 arguments:
                sni_ssl_socket: ssl.SSLSocket, SSL socket object.
                sni_destination_name: string, domain name from SNI.
                sni_ssl_context: ssl.SSLContext, SSL context object.

            These parameters are default for any SNI handler function, so you can use them in your custom function.

        :param sni_use_default_callback_function: boolean, if True, default callback function will be used.
            The function will set the 'server_hostname' for the socket with the domain name from SNI.
            The example in 'sni_custom_callback_function' parameter is the function that will be used.
        :param sni_use_default_callback_function_extended: boolean, if True, default callback function will be used
            with extended functionality. This feature will handle all the features and parameters that are set in
            the SocketWrapper object that are related to SNI. THis includes certificate management for each domain,
            adding new domains to the default certificate, creating new certificates for each domain, etc.
            This feature also utilizes the 'request_domain_queue' parameter to get the domain name that was requested
            from the DNS server (atomicshop.wrappers.socketw.dns_server).
        :param sni_add_new_domains_to_default_server_certificate: boolean, if True, new domains that hit the tcp
            server will be added to default server certificate.
        :param sni_create_server_certificate_for_each_domain: boolean, if True, server certificate will be
            created and used for each domain that hit the tcp server.
        :param sni_get_server_certificate_from_server_socket: boolean, if True, server certificate will be
            downloaded from the server socket.
        :param sni_server_certificate_from_server_socket_download_directory: string, path to directory where
            server certificate will be downloaded from the server socket.
        :param default_server_certificate_name: default server certificate name.
        :param default_certificate_domain_list: list of string, domains to create the default certificate with.
        :param default_server_certificate_directory: string, path to directory where default certificate file
            will be stored.
        :param sni_server_certificates_cache_directory: string, path to directory where all server certificates for
            each domain will be created.
        :param skip_extension_id_list: list of string, list of extension IDs that will be skipped when processing
            the certificate from the server socket.
            Example: ['1.3.6.1.5.5.7.3.2', '2.5.29.31', '1.3.6.1.5.5.7.1.1']
        :param custom_server_certificate_usage: boolean, if True, custom server certificate will be used.
        :param custom_server_certificate_path: string, path to custom server certificate.
        :param custom_private_key_path: string, path to custom private key.
            server certificates from the server socket.
        :param get_process_name: boolean, if the process name and command line should be gathered from the socket.
            If the socket came from remote host we will try ti get the process name from the remote host by SSH.
            By default, we don't get the process name, because we're using psutil to get the process name and command
            line, but if the process is protected by the system, then command line will be empty.
            It's up to user to decide if to run the script with root privileges or not, this is only relevant if
            the script is running on the same host.
        :param ssh_user: string, SSH username that will be used to connect to remote host.
        :param ssh_pass: string, SSH password that will be used to connect to remote host.
        :param ssh_script_to_execute: string, script that will be executed to get the process name on ssh remote host.
        :param logs_directory: string, path to directory where daily statistics.csv files and all the other logger
            files will be stored. After you initialize the SocketWrapper object, you can get the statistics_writer
            object from it and use it to write statistics to the file in a worker thread.

            socket_wrapper_instance = SocketWrapper(...)
            statistics_writer = socket_wrapper_instance.statistics_writer

            statistics_writer: statistics_csv.StatisticsCSVWriter object, there is a logger object that
                will be used to write the statistics file.
        :param logger_name: string, name of the logger that will be used to log messages.
        :param logger_queue: multiprocessing.Queue, queue that will be used to log messages in multiprocessing.
            You need to start the logger listener in the main process to handle the queue.
        :param statistics_logger_name: string, name of the logger that will be used to log statistics.
        :param statistics_logger_queue: multiprocessing.Queue, queue that will be used to log statistics in
            multiprocessing. You need to start the logger listener in the main process to handle the queue.
        :param exceptions_logger_name: string, name of the logger that will be used to log exceptions.
        :param exceptions_logger_queue: multiprocessing.Queue, queue that will be used to log exceptions in
            multiprocessing. You need to start the logger listener in the main process to handle the queue.
        :param enable_sslkeylogfile_env_to_client_ssl_context: boolean, if True, each client SSL context
            that will be created by the SocketWrapper will have save the SSL handshake keys to the file
            defined in 'sslkeylog_file_path' parameter.
        :param sslkeylog_file_path: string, path to file where SSL handshake keys will be saved.
            If not provided and 'enable_sslkeylogfile_env_to_client_ssl_context' is True, then
            the environment variable 'SSLKEYLOGFILE' will be used.
        :param print_kwargs: dict, additional arguments to pass to the print function.
        """

        self.ip_address: str = ip_address
        self.port: int = port
        self.engine: initialize_engines.ModuleCategory = engine
        self.ca_certificate_name: str = ca_certificate_name
        self.ca_certificate_filepath: str = ca_certificate_filepath
        self.ca_certificate_crt_filepath: str = ca_certificate_crt_filepath
        self.install_ca_certificate_to_root_store: bool = install_ca_certificate_to_root_store
        self.uninstall_unused_ca_certificates_with_ca_certificate_name: bool = \
            uninstall_unused_ca_certificates_with_ca_certificate_name
        self.default_server_certificate_usage: bool = default_server_certificate_usage
        self.default_server_certificate_name: str = default_server_certificate_name
        self.default_certificate_domain_list: list = default_certificate_domain_list
        self.default_server_certificate_directory: str = default_server_certificate_directory
        self.sni_custom_callback_function: Callable[..., Any] = sni_custom_callback_function
        self.sni_use_default_callback_function: bool = sni_use_default_callback_function
        self.sni_use_default_callback_function_extended: bool = sni_use_default_callback_function_extended
        self.sni_add_new_domains_to_default_server_certificate: bool = sni_add_new_domains_to_default_server_certificate
        self.sni_create_server_certificate_for_each_domain: bool = sni_create_server_certificate_for_each_domain
        self.sni_server_certificates_cache_directory: str = sni_server_certificates_cache_directory
        self.sni_get_server_certificate_from_server_socket: bool = sni_get_server_certificate_from_server_socket
        self.sni_server_certificate_from_server_socket_download_directory: str = \
            sni_server_certificate_from_server_socket_download_directory
        self.skip_extension_id_list: list = skip_extension_id_list
        self.custom_server_certificate_usage: bool = custom_server_certificate_usage
        self.custom_server_certificate_path: str = custom_server_certificate_path
        self.custom_private_key_path: str = custom_private_key_path
        self.get_process_name: bool = get_process_name
        self.ssh_user: str = ssh_user
        self.ssh_pass: str = ssh_pass
        self.ssh_script_to_execute = ssh_script_to_execute
        self.forwarding_dns_service_ipv4_list___only_for_localhost = (
            forwarding_dns_service_ipv4_list___only_for_localhost)
        self.enable_sslkeylogfile_env_to_client_ssl_context: bool = (
            enable_sslkeylogfile_env_to_client_ssl_context)
        self.sslkeylog_file_path: str = sslkeylog_file_path
        self.print_kwargs: dict = print_kwargs

        self.socket_object = None

        # Server certificate file path that will be loaded into SSL Context.
        self.server_certificate_file_path: str = str()
        self.server_private_key_file_path = None

        self.sni_received_dict: dict = dict()
        self.sni_execute_extended: bool = False
        self.certauth_wrapper = None

        # Defining list of threads, so we can "join()" them in the end all at once.
        self.threads_list: list = list()

        # Defining listening sockets list, which will be used with "select" library in 'loop_for_incoming_sockets'.
        self.listening_sockets: list = list()

        # Defining 'ssh_script_string' variable, which will be used to process SSH scripts.
        self.ssh_script_processor = None
        if self.get_process_name:
            # noinspection PyTypeChecker
            self.package_processor: package_mains_processor.PackageMainsProcessor | None = package_mains_processor.PackageMainsProcessor(script_file_stem=self.ssh_script_to_execute)

        else:
            self.package_processor = None

        # We will initialize it during the first 'get_process_name' function call.
        self.ssh_client: ssh_remote.SSHRemote | None = None

        # If logs directory was not set, we will use the working directory.
        if not logs_directory:
            logs_directory = str(Path.cwd() / LOGS_DIRECTORY_NAME)
        self.logs_directory: str = logs_directory

        if not logger_name:
            logger_name = 'SocketWrapper'
        self.logger_name: str = logger_name
        self.logger_name_listener: str = f"{logger_name}.listener"

        if loggingw.is_logger_exists(self.logger_name_listener):
            self.logger = loggingw.get_logger_with_level(self.logger_name_listener)
        elif not logger_queue:
            _ = loggingw.create_logger(
                logger_name=logger_name,
                directory_path=self.logs_directory,
                add_stream=True,
                add_timedfile_with_internal_queue=True,
                formatter_streamhandler='DEFAULT',
                formatter_filehandler='DEFAULT'
            )

            self.logger = loggingw.get_logger_with_level(self.logger_name_listener)
        else:
            _ = loggingw.create_logger(
                logger_name=logger_name,
                add_queue_handler=True,
                log_queue=logger_queue
            )
            self.logger = loggingw.get_logger_with_level(self.logger_name_listener)

        self.statistics_writer = statistics_csv.StatisticsCSVWriter(
            logger_name=statistics_logger_name,
            directory_path=self.logs_directory,
            log_queue=statistics_logger_queue,
            add_queue_handler_no_listener_multiprocessing=True
        )

        if not exceptions_logger_name:
            exceptions_logger_name = 'SocketWrapperExceptions'

        self.exceptions_logger = loggingw.ExceptionCsvLogger(
            logger_name=exceptions_logger_name,
            directory_path=self.logs_directory,
            log_queue=exceptions_logger_queue,
            add_queue_handler_no_listener_multiprocessing=True
        )

        self.test_config()

    def test_config(self):
        if self.sni_custom_callback_function and (
                self.sni_use_default_callback_function or self.sni_use_default_callback_function_extended):
            message = "You can't use both custom and default SNI function at the same time."
            raise SocketWrapperConfigurationValuesError(message)

        if self.sni_use_default_callback_function_extended and not self.sni_use_default_callback_function:
            message = "You can't use extended SNI function without default SNI function."
            raise SocketWrapperConfigurationValuesError(message)

        if self.sni_use_default_callback_function and self.sni_custom_callback_function:
            message = \
                "You can't set both [sni_use_default_callback_function = True] and [sni_custom_callback_function]."
            raise SocketWrapperConfigurationValuesError(message)

        try:
            booleans.is_only_1_true_in_list(
                booleans_list_of_tuples=[
                    (self.default_server_certificate_usage, 'default_server_certificate_usage'),
                    (self.sni_create_server_certificate_for_each_domain,
                     'sni_create_server_certificate_for_each_domain'),
                    (self.custom_server_certificate_usage, 'custom_server_certificate_usage')
                ],
                raise_if_all_false=True
            )
        except ValueError as e:
            raise SocketWrapperConfigurationValuesError(str(e))

        if not self.default_server_certificate_usage and \
                self.sni_add_new_domains_to_default_server_certificate:
            message = "No point setting [sni_add_new_domains_to_default_server_certificate = True]\n" \
                      "If you're not going to use default certificates [default_server_certificate_usage = False]"
            raise SocketWrapperConfigurationValuesError(message)

        if self.sni_get_server_certificate_from_server_socket and \
                not self.sni_create_server_certificate_for_each_domain:
            message = "You set [sni_get_server_certificate_from_server_socket = True],\n" \
                      "But you didn't set [sni_create_server_certificate_for_each_domain = True]."
            raise SocketWrapperConfigurationValuesError(message)

        if self.custom_server_certificate_usage and \
                not self.custom_server_certificate_path:
            message = "You set [custom_server_certificate_usage = True],\n" \
                      "But you didn't set [custom_server_certificate_path]."
            raise SocketWrapperConfigurationValuesError(message)

        # If 'custom_certificate_usage' was set to 'True'.
        if self.custom_server_certificate_usage:
            # Check file existence.
            if not filesystem.is_file_exists(file_path=self.custom_server_certificate_path):
                message = f"File not found: {self.custom_server_certificate_path}"
                print_api(message, color='red', logger=self.logger)
                return 1

            # And if 'custom_private_key_path' field was populated in [advanced] section, we'll check its existence.
            if self.custom_private_key_path:
                # Check private key file existence.
                if not filesystem.is_file_exists(file_path=self.custom_private_key_path):
                    message = f"File not found: {self.custom_private_key_path}"
                    print_api(message, color='red', logger=self.logger)
                    return 1

        # Check if the port is in usable port range.
        if not (0 < self.port < 65536):
            message = f"Port number [{self.port}] is out of usable port range (1-65535)."
            raise SocketWrapperConfigurationValuesError(message)

        # Checking if listening address is in use.
        listening_check_list = [f"{self.ip_address}:{self.port}"]
        port_in_use = psutil_networks.get_processes_using_port_list(listening_check_list)
        if port_in_use:
            error_messages: list = list()
            for port, process_info in port_in_use.items():
                error_messages.append(f"Port [{port}] is already in use by process: {process_info}")
            raise SocketWrapperPortInUseError("\n".join(error_messages))

        # Creating CA certificate if it doesn't exist.
        if not filesystem.is_file_exists(file_path=self.ca_certificate_filepath):
            # Initialize CertAuthWrapper.
            ca_certificate_directory: str = str(Path(self.ca_certificate_filepath).parent)
            certauth_wrapper = certauthw.CertAuthWrapper(
                ca_certificate_name=self.ca_certificate_name,
                ca_certificate_filepath=self.ca_certificate_filepath,
                server_certificate_directory=ca_certificate_directory
            )

            # Create CA certificate if it doesn't exist.
            certauth_wrapper.create_use_ca_certificate()

            certificates.write_crt_certificate_file_in_pem_format_from_pem_file(
                pem_file_path=self.ca_certificate_filepath,
                crt_file_path=self.ca_certificate_crt_filepath)

            # If someone removed the CA certificate file manually, and now it was created, we also need to
            # clear the cached certificates.
            try:
                shutil.rmtree(self.sni_server_certificates_cache_directory)
            # If the directory doesn't exist it will throw an exception, which is OK.
            except FileNotFoundError:
                pass

            os.makedirs(self.sni_server_certificates_cache_directory, exist_ok=True)
            print_api("Removed cached server certificates.", logger=self.logger)
        else:
            os.makedirs(self.sni_server_certificates_cache_directory, exist_ok=True)

        if self.install_ca_certificate_to_root_store:
            if not self.ca_certificate_filepath:
                message = "You set [install_ca_certificate_to_root_store = True],\n" \
                          "But you didn't set [ca_certificate_filepath]."
                raise SocketWrapperConfigurationValuesError(message)

            # Before installation check if there are any unused certificates with the same name.
            if self.uninstall_unused_ca_certificates_with_ca_certificate_name:
                # Check how many certificates with our ca certificate name are installed.
                is_installed_by_name, certificate_list_by_name = certificates.is_certificate_in_store(
                    issuer_name=self.ca_certificate_name)
                # If there is more than one certificate with the same name, delete them all.
                if is_installed_by_name and len(certificate_list_by_name) > 1:
                    message = f"More than one certificate with the same issuer name is installed. Removing all..."
                    print_api(message, color='yellow', logger=self.logger)
                    certificates.delete_certificate_by_issuer_name(self.ca_certificate_name)
                # If there is only one certificate with the same name, check if it is the same certificate.
                elif is_installed_by_name and len(certificate_list_by_name) == 1:
                    is_installed_by_file, certificate_list_by_file = certificates.is_certificate_in_store(
                        certificate=self.ca_certificate_filepath, by_cert_thumbprint=True, by_cert_issuer=True,
                        print_kwargs=self.print_kwargs)
                    # If the certificate is not the same, delete it.
                    if not is_installed_by_file:
                        if not permissions.is_admin():
                            raise SocketWrapperConfigurationValuesError(
                                "You need to run the script with admin rights to uninstall the unused certificates.")
                        message = (
                            f"Certificate with the same issuer name is installed, but it is not the same certificate. "
                            f"Removing...")
                        print_api(message, color='yellow', logger=self.logger)
                        certificates.delete_certificate_by_issuer_name(
                            self.ca_certificate_name, store_location="ROOT", print_kwargs={'logger': self.logger})

            if self.install_ca_certificate_to_root_store:
                # Install CA certificate to the root store if it is not installed.
                is_installed_by_file, certificate_list_by_file = certificates.is_certificate_in_store(
                    certificate=self.ca_certificate_filepath, by_cert_thumbprint=True, by_cert_issuer=True,
                    print_kwargs=self.print_kwargs
                )
                if not is_installed_by_file:
                    if not permissions.is_admin():
                        raise SocketWrapperConfigurationValuesError(
                            "You need to run the script with admin rights to install the CA certificate.")
                    certificates.install_certificate_file(
                        self.ca_certificate_filepath, store_location="ROOT",
                        print_kwargs={'logger': self.logger, 'color': 'blue'})

    # Creating listening sockets.
    def create_socket_ipv4_tcp(self, ip_address: str, port: int):
        self.sni_execute_extended = True
        self.socket_object = creator.create_socket_ipv4_tcp()
        creator.add_reusable_address_option(self.socket_object)
        creator.bind_socket_with_ip_port(self.socket_object, ip_address, port, logger=self.logger)
        creator.set_listen_on_socket(self.socket_object, logger=self.logger)

        return self.socket_object

    def start_listening_socket(
            self,
            callable_function: Callable[..., Any],
            callable_args: tuple = ()
    ):
        """
        Start listening on a single socket with given IP address and port.
        This function is used to start listening on a single socket, for example, when you want to listen on a specific
        IP address and port.

        :param callable_function: callable, function that you want to execute when client
            socket received by 'accept()' and connection has been made.
        :param callable_args: tuple, that will be passed to 'callable_function' when it will be called.
        :return: None
        """

        if self.engine:
            acceptor_name: str = f"acceptor-{self.engine.engine_name}-{self.ip_address}:{self.port}"
        else:
            acceptor_name: str = f"acceptor-{self.ip_address}:{self.port}"

        socket_by_port = self.create_socket_ipv4_tcp(self.ip_address, self.port)
        threading.Thread(
            target=self.listening_socket_loop,
            args=(socket_by_port, callable_function, callable_args),
            name=acceptor_name,
            daemon=True
        ).start()

    def listening_socket_loop(
            self,
            listening_socket_object: socket.socket,
            callable_function: Callable[..., Any],
            callable_args=()
    ):
        """
        Loop to wait for new connections, accept them and send to new threads.
        The boolean variable was declared True in the beginning of the script and will be set to False if the process
        will be killed or closed.

        :param listening_socket_object: listening socket that was created with bind.
        :param callable_function: callable, function that you want to execute when client
            socket received by 'accept()' and connection has been made.
        :param callable_args: tuple, that will be passed to 'function_reference' when it will be called.
            Your function should be able to accept these arguments before the 'callable_args' tuple:
            (client_socket, process_name, is_tls, domain_from_dns_server).
            Meaning that 'callable_args' will be added to the end of the arguments tuple like so:
            (client_socket, process_name, is_tls, tls_type, tls_version, domain_from_dns_server,
            *callable_args).

            client_socket: socket, client socket that was accepted.
            process_name: string, process name that was gathered from the socket.
            is_tls: boolean, if the socket is SSL/TLS.
            domain_from_dns_server: string, domain that was requested from DNS server.
        :return:
        """

        listening_sockets: list = [listening_socket_object]

        while True:
            engine_name: str = ''
            source_ip: str = ''
            source_hostname: str = ''
            dest_port: int = 0
            process_name: str = ''
            domain_from_engine: str = ''

            try:
                # Using "select.select" which is currently the only API function that works on all
                # operating system types: Windows / Linux / BSD.
                # To accept connection, we don't need "writable" and "exceptional", since "readable" holds the currently
                # connected socket.
                readable, writable, exceptional = select.select(listening_sockets, [], [])
                listening_socket_object = readable[0]

                listening_ip, listening_port = listening_socket_object.getsockname()

                # Get the domain to connect on this process in case on no SNI provided.
                for domain, ip_port_dict in self.engine.domain_target_dict.items():
                    if ip_port_dict['ip'] == listening_ip:
                        domain_from_engine = domain
                        break
                # If there was no domain found, try to find the IP address for port.
                if not domain_from_engine:
                    for port, file_or_ip in self.engine.port_target_dict.items():
                        if file_or_ip['ip'] == listening_ip:
                            # Get the value from the 'on_port_connect' dictionary.
                            address_or_file_path: str = self.engine.on_port_connect[str(listening_port)]
                            ip_port_address_from_config: tuple = initialize_engines.get_ipv4_from_engine_on_connect_port(
                                address_or_file_path)
                            if not ip_port_address_from_config:
                                raise ValueError(
                                    f"Invalid IP address or file path in 'on_port_connect' for port "
                                    f"{listening_port}: {address_or_file_path}"
                                )

                            domain_from_engine = ip_port_address_from_config[0]

                            break

                self.logger.info(f"Requested domain setting: {domain_from_engine}")

                engine_name = get_engine_name(domain_from_engine, [self.engine])

                # Wait from any connection on "accept()".
                # 'client_socket' is socket or ssl socket, 'client_address' is a tuple (ip_address, port).
                client_socket, client_address, accept_error_message = accepter.accept_connection_with_error(
                    listening_socket_object, domain_from_dns_server=domain_from_engine,
                    print_kwargs={'logger': self.logger})

                source_ip: str = client_address[0]
                source_port: int = client_address[1]
                dest_port: int = listening_socket_object.getsockname()[1]

                message: str = f"Accepted connection from [{source_ip}:{source_port}] to [{listening_ip}:{dest_port}] | domain: {domain_from_engine}"
                print_api(message, logger=self.logger)

                # Not always there will be a hostname resolved by the IP address, so we will leave it empty if it fails.
                try:
                    source_hostname = socket.gethostbyaddr(source_ip)[0]
                    source_hostname = source_hostname.lower()
                except socket.herror:
                    pass

                # This is the earliest stage to ask for process name.
                # SSH Remote / LOCALHOST script execution to identify process section.
                # If 'get_process_name' was set to True, then this will be executed.
                if self.get_process_name:
                    # Initializing SSHRemote class if not initialized.
                    if self.ssh_client is None:
                        self.ssh_client = ssh_remote.SSHRemote(
                            ip_address=source_ip, username=self.ssh_user, password=self.ssh_pass, logger=self.logger)

                    # Get the process name from the socket.
                    get_command_instance = process_getter.GetCommandLine(
                        client_ip=source_ip,
                        client_port=source_port,
                        package_processor=self.package_processor,
                        ssh_client=self.ssh_client,
                        logger=self.logger)
                    process_name = get_command_instance.get_process_name(print_kwargs={'logger': self.logger})

                    # from ..pywin32w.win_event_log import fetch
                    # events = fetch.get_latest_events(
                    #     server_ip=source_ip,
                    #     username=self.ssh_user,
                    #     password=self.ssh_pass,
                    #     log_name='Security',
                    #     count=50,
                    #     event_id_list=[5156]
                    # )
                    #
                    # source_port = client_address[1]
                    # for event in events:
                    #     if source_port == event['StringsDict']['Source Port']:
                    #         process_name = event['StringsDict']['Application Name']
                    #         break
                    #
                    # if process_name == '':
                    #     raise RuntimeError("Failed to get process name from the remote host via Event Log.")

                # If 'accept()' function worked well, SSL worked well, then 'client_socket' won't be empty.
                if client_socket:
                    # Get the protocol type from the socket.
                    is_tls: bool = False

                    try:
                        tls_properties = ssl_base.is_tls(client_socket, timeout=1)
                    except TimeoutError:
                        error: str = "TimeoutError: TLS detection timed out. Dropping accepted socket."
                        self.logger.error(error)

                        self.statistics_writer.write_accept_error(
                            engine=engine_name,
                            source_host=source_hostname,
                            source_ip=source_ip,
                            error_message=error,
                            dest_port=str(dest_port),
                            host=domain_from_engine,
                            process_name=process_name)

                        client_socket.close()
                        continue

                    if tls_properties:
                        is_tls = True
                        tls_type, tls_version = tls_properties
                    else:
                        tls_type, tls_version = None, None

                    # If 'is_tls' is True.
                    ssl_client_socket = None
                    if is_tls:
                        sni_handler = sni.SNISetup(
                            default_server_certificate_usage=self.default_server_certificate_usage,
                            default_server_certificate_name=self.default_server_certificate_name,
                            default_certificate_domain_list=self.default_certificate_domain_list,
                            default_server_certificate_directory=self.default_server_certificate_directory,
                            sni_custom_callback_function=self.sni_custom_callback_function,
                            sni_use_default_callback_function=self.sni_use_default_callback_function,
                            sni_use_default_callback_function_extended=self.sni_use_default_callback_function_extended,
                            sni_add_new_domains_to_default_server_certificate=(
                                self.sni_add_new_domains_to_default_server_certificate),
                            sni_server_certificates_cache_directory=self.sni_server_certificates_cache_directory,
                            sni_create_server_certificate_for_each_domain=(
                                self.sni_create_server_certificate_for_each_domain),
                            sni_get_server_certificate_from_server_socket=(
                                self.sni_get_server_certificate_from_server_socket),
                            sni_server_certificate_from_server_socket_download_directory=(
                                self.sni_server_certificate_from_server_socket_download_directory),
                            skip_extension_id_list=self.skip_extension_id_list,
                            ca_certificate_name=self.ca_certificate_name,
                            ca_certificate_filepath=self.ca_certificate_filepath,
                            custom_server_certificate_usage=self.custom_server_certificate_usage,
                            custom_server_certificate_path=self.custom_server_certificate_path,
                            custom_private_key_path=self.custom_private_key_path,
                            domain_from_dns_server=domain_from_engine,
                            forwarding_dns_service_ipv4_list___only_for_localhost=(
                                self.forwarding_dns_service_ipv4_list___only_for_localhost),
                            tls=is_tls,
                            exceptions_logger=self.exceptions_logger,
                            enable_sslkeylogfile_env_to_client_ssl_context=self.enable_sslkeylogfile_env_to_client_ssl_context,
                            sslkeylog_file_path=self.sslkeylog_file_path
                        )

                        ssl_client_socket, accept_error_message = \
                            sni_handler.wrap_socket_with_ssl_context_server_sni_extended(
                                client_socket,
                                print_kwargs={'logger': self.logger}
                            )

                        if ssl_client_socket:
                            # Handshake is done at this point, so version/cipher are available
                            self.logger.info(
                                f"TLS version={ssl_client_socket.version()} cipher={ssl_client_socket.cipher()}"
                            )

                        if accept_error_message:
                            # Write statistics after wrap is there was an error.
                            self.statistics_writer.write_accept_error(
                                engine=engine_name,
                                source_host=source_hostname,
                                source_ip=source_ip,
                                error_message=accept_error_message,
                                dest_port=str(dest_port),
                                host=domain_from_engine,
                                process_name=process_name)

                            continue

                        # Get the real tls version after connection is wrapped.
                        tls_version = ssl_client_socket.version()

                        # If the 'domain_from_dns_server' is empty, it means that the 'engine_name' is not set.
                        # In this case we will set the 'engine_name' to from the SNI.
                        if engine_name == '':
                            sni_hostname: str = ssl_client_socket.server_hostname
                            if sni_hostname:
                                engine_name = get_engine_name(sni_hostname, [self.engine])

                    # Create new arguments tuple that will be passed, since client socket and process_name
                    # are gathered from SocketWrapper.
                    if ssl_client_socket:
                        # In order to use the same object, it needs to get nullified first, since the old instance
                        # will not get overwritten. Though it still will show in the memory as SSLSocket, it will not
                        # be handled as such, but as regular raw socket.
                        # noinspection PyUnusedLocal
                        client_socket = None
                        client_socket = ssl_client_socket
                    thread_args = (
                        (client_socket, process_name, is_tls, tls_type, tls_version, domain_from_engine, self.statistics_writer, [self.engine]) +
                         callable_args)

                    # Creating thread for each socket
                    thread_current = threading.Thread(
                        target=before_socket_thread_worker,
                        args=(callable_function, thread_args, self.exceptions_logger),
                        daemon=True
                    )
                    thread_current.start()
                    # Append to list of threads, so they can be "joined" later
                    self.threads_list.append(thread_current)

                    # 'thread_callable_args[1][0]' is the client socket.
                    client_address = socket_base.get_source_address_from_socket(client_socket)

                    self.logger.info(f"Accepted connection, thread created {client_address}. Continue listening...")
                # Else, if no client_socket was opened during, accept, then print the error.
                else:
                    # Write statistics after accept.
                    self.statistics_writer.write_accept_error(
                        engine=engine_name,
                        source_host=source_hostname,
                        source_ip=source_ip,
                        error_message=accept_error_message,
                        dest_port=str(dest_port),
                        host=domain_from_engine,
                        process_name=process_name)
            # Sometimes paramiko SSH connection return EOFError on connection reset, so we need to catch it separately.
            # Basically all these exceptions mean that there was a problem with the connection in some way, besides the
            # python not being found, but it also can be that there was a problem with the connection and the script
            # was cut mid-action.
            except (
                ConnectionResetError, EOFError, TimeoutError,
                paramiko.ssh_exception.SSHException, paramiko.ssh_exception.NoValidConnectionsError,
                ssh_remote.SSHRemoteWrapperNoPythonFound
            ) as e:
                exception_string: str = tracebacks.get_as_string()
                full_string: str = f"{str(e)} | {exception_string}"
                self.statistics_writer.write_accept_error(
                    engine=engine_name,
                    source_host=source_hostname,
                    source_ip=source_ip,
                    error_message=full_string,
                    dest_port=str(dest_port),
                    host=domain_from_engine,
                    process_name=process_name)
            except Exception as e:
                _ = e
                exception_string: str = tracebacks.get_as_string()
                full_string: str = f"Engine: [{engine_name}] | {exception_string}"
                self.exceptions_logger.write(full_string)


def before_socket_thread_worker(
        callable_function: Callable[..., Any],
        callable_args: tuple,
        exceptions_logger: loggingw.ExceptionCsvLogger = None
):
    """
    Function that will be executed before the thread is started.
    :param callable_function: callable, function that will be executed in the thread.
    :param callable_args: tuple, arguments that will be passed to the function.
    :param exceptions_logger: loggingw.ExceptionCsvLogger, logger object that will be used to log exceptions.
    :return:
    """

    try:
        callable_function(*callable_args)
    except Exception as e:
        exceptions_logger.write(e, custom_exception_attribute='engine_name', custom_exception_attribute_placement='before')


def get_engine_name(domain: str, engine_list: list):
    """
    Function that will get the engine name from the domain name.
    :param domain: string, domain name.
    :param engine_list: list that contains the engine names and domains.
    :return: string, engine name.
    """

    engine_name: str = ''
    for engine in engine_list:
        # Get engine name by domain.
        if domain in engine.domain_target_dict:
            engine_name = engine.engine_name

        # If didn't find by domain, try to find by port.
        if engine_name == '':
            for port, ip_port_to_connect_value in engine.on_port_connect.items():
                ipv4_to_connect, _ = initialize_engines.get_ipv4_from_engine_on_connect_port(ip_port_to_connect_value)
                if ipv4_to_connect == domain:
                    engine_name = engine.engine_name
                    break

    return engine_name
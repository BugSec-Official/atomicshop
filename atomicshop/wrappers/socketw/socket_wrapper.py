import threading
import select
from typing import Literal, Union
from pathlib import Path
import logging
import socket
import multiprocessing

from ..psutilw import networks
from ..certauthw import certauthw
from ..loggingw import loggingw
from ...script_as_string_processor import ScriptAsStringProcessor
from ...permissions import permissions
from ... import queues, filesystem, certificates
from ...basics import booleans
from ...print_api import print_api

from . import base, creator, get_process, accepter, statistics_csv, ssl_base, sni


class SocketWrapperPortInUseError(Exception):
    pass


class SocketWrapperConfigurationValuesError(Exception):
    pass


SNI_QUEUE = queues.NonBlockQueue()


class SocketWrapper:
    def __init__(
            self,
            listening_interface: str,
            listening_port_list: list[int],
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
            sni_custom_callback_function: callable = None,
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
                Literal[
                    'process_from_port',
                    'process_from_ipv4'
                ],
                None
            ] = None,
            logger: logging.Logger = None,
            exceptions_logger: loggingw.ExceptionCsvLogger = None,
            statistics_logs_directory: str = None,
            request_domain_from_dns_server_queue: multiprocessing.Queue = None,
            engines_domains: dict = None
    ):
        """
        Socket Wrapper class that will be used to create sockets, listen on them, accept connections and send them to
        new threads.

        :param listening_interface: string, interface that will be listened on.
            Example: '0.0.0.0'. For all interfaces.
        :param listening_port_list: list, of ports that will be listened on.
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
        :param logger: logging.Logger object, logger object that will be used to log messages.
            If not provided, logger will be created with default settings saving logs to the
            'statistics_logs_directory'.
        :param exceptions_logger: loggingw.ExceptionCsvLogger object, logger object that will be used to log exceptions.
            If not provided, logger will be created with default settings and will save exceptions to the
            'statistics_logs_directory'.
        :param statistics_logs_directory: string, path to directory where daily statistics.csv files will be stored.
            After you initialize the SocketWrapper object, you can get the statistics_writer object from it and use it
            to write statistics to the file in a worker thread.

            socket_wrapper_instance = SocketWrapper(...)
            statistics_writer = socket_wrapper_instance.statistics_writer

            statistics_writer: statistics_csv.StatisticsCSVWriter object, there is a logger object that
                will be used to write the statistics file.
        :param request_domain_from_dns_server_queue: multiprocessing queue that will be used
            to get the domain name that was requested from the DNS server (atomicshop.wrappers.socketw.dns_server).
            This is used to get the domain name that got to the DNS server and set it to the socket in case SNI
            was empty (in the SNIHandler class to set the 'server_hostname' for the socket).
        :param engines_domains: dictionary of engines that will be used to process the requests. Example:
            [
                {'this_is_engine_name': ['example.com', 'example.org']},
                {'this_is_engine_name2': ['example2.com', 'example2.org']}
            ]

            the 'engine_name' for statistics.csv file will be taken from the key of the dictionary, while correlated
            by the domain name from the list in the dictionary.
        """

        self.listening_interface: str = listening_interface
        self.listening_port_list: list[int] = listening_port_list
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
        self.sni_custom_callback_function: callable = sni_custom_callback_function
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
        self.logger = logger
        self.statistics_logs_directory: str = statistics_logs_directory
        self.forwarding_dns_service_ipv4_list___only_for_localhost = (
            forwarding_dns_service_ipv4_list___only_for_localhost)
        self.request_domain_from_dns_server_queue: multiprocessing.Queue = request_domain_from_dns_server_queue
        self.engines_domains: dict = engines_domains

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

        # Defining 'ssh_script_processor' variable, which will be used to process SSH scripts.
        self.ssh_script_processor = None
        if self.get_process_name:
            # noinspection PyTypeChecker
            self.ssh_script_processor = \
                ScriptAsStringProcessor().read_script_to_string(self.ssh_script_to_execute)

        self.statistics_writer = statistics_csv.StatisticsCSVWriter(
            statistics_directory_path=self.statistics_logs_directory)

        if not self.logger:
            self.logger = loggingw.create_logger(
                logger_name='SocketWrapper',
                directory_path=self.statistics_logs_directory,
                add_stream=True,
                add_timedfile_with_internal_queue=True,
                formatter_streamhandler='DEFAULT',
                formatter_filehandler='DEFAULT'
            )

        if not exceptions_logger:
            self.exceptions_logger = loggingw.ExceptionCsvLogger(
                logger_name='SocketWrapperExceptions',
                directory_path=self.statistics_logs_directory
            )
        else:
            self.exceptions_logger = exceptions_logger

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

        ips_ports: list[str] = list()
        for port in self.listening_port_list:
            ips_ports.append(f"{self.listening_interface}:{port}")

        port_in_use = networks.get_processes_using_port_list(ips_ports)
        if port_in_use:
            error_messages: list = list()
            for port, process_info in port_in_use.items():
                error_messages.append(f"Port [{port}] is already in use by process: {process_info}")
            raise SocketWrapperPortInUseError("\n".join(error_messages))

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
                        certificate=self.ca_certificate_filepath, by_cert_thumbprint=True, by_cert_issuer=True)
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
                    certificate=self.ca_certificate_filepath, by_cert_thumbprint=True, by_cert_issuer=True)
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

    def create_tcp_listening_socket_list(self, overwrite_list: bool = False):
        # If 'overwrite_list' was set to 'True', we will create new list. The default is 'False', since it is meant to`
        # add new sockets to already existing ones.
        if overwrite_list:
            self.listening_sockets = list()

        # Creating a socket for each port in the list set in configuration file
        for port in self.listening_port_list:
            socket_by_port = self.create_socket_ipv4_tcp(
                self.listening_interface, port)

            self.listening_sockets.append(socket_by_port)

    def loop_for_incoming_sockets(
            self,
            reference_function_name,
            reference_function_args=(),
            listening_socket_list: list = None,
            pass_function_reference_to_thread: bool = True
    ):
        """
        Loop to wait for new connections, accept them and send to new threads.
        The boolean variable was declared True in the beginning of the script and will be set to False if the process
        will be killed or closed.

        :param reference_function_name: callable, function reference that you want to execute when client
            socket received by 'accept()' and connection has been made.
        :param reference_function_args: tuple, that will be passed to 'function_reference' when it will be called.
            Your function should be able to accept these arguments before the 'reference_function_args' tuple:
            (client_socket, process_name, is_tls, domain_from_dns_server).
            Meaning that 'reference_function_args' will be added to the end of the arguments tuple like so:
            (client_socket, process_name, is_tls, tls_type, tls_version, domain_from_dns_server,
            *reference_function_args).

            client_socket: socket, client socket that was accepted.
            process_name: string, process name that was gathered from the socket.
            is_tls: boolean, if the socket is SSL/TLS.
            domain_from_dns_server: string, domain that was requested from DNS server.
        :param listening_socket_list: list, of sockets that you want to listen on.
        :param pass_function_reference_to_thread: boolean, that sets if 'function_reference' will be
            executed as is, or passed to thread. 'function_reference' can include passing to a thread,
            but you don't have to use it, since SocketWrapper can do it for you.
        :return:
        """

        # If 'listening_socket_list' wasn't specified and 'self.listening_sockets' is not empty.
        if not listening_socket_list and self.listening_sockets:
            # Then assign 'self.listening_sockets'.
            listening_socket_list = self.listening_sockets

        while True:
            try:
                # Using "select.select" which is currently the only API function that works on all
                # operating system types: Windows / Linux / BSD.
                # To accept connection, we don't need "writable" and "exceptional", since "readable" holds the currently
                # connected socket.
                readable, writable, exceptional = select.select(listening_socket_list, [], [])
                listening_socket_object = readable[0]

                # Get the domain queue. Tried using "Queue.Queue" object, but it stomped the SSL Sockets
                # from accepting connections.
                domain_from_dns_server = None
                if self.request_domain_from_dns_server_queue is not None:
                    domain_from_dns_server = self.request_domain_from_dns_server_queue.get()
                    self.logger.info(f"Requested domain from DNS Server: {domain_from_dns_server}")

                # Wait from any connection on "accept()".
                # 'client_socket' is socket or ssl socket, 'client_address' is a tuple (ip_address, port).
                client_socket, client_address, accept_error_message = accepter.accept_connection_with_error(
                    listening_socket_object, domain_from_dns_server=domain_from_dns_server,
                    print_kwargs={'logger': self.logger})

                # This is the earliest stage to ask for process name.
                # SSH Remote / LOCALHOST script execution to identify process section.
                # If 'get_process_name' was set to True, then this will be executed.
                process_name = None
                if self.get_process_name:
                    # Get the process name from the socket.
                    get_command_instance = get_process.GetCommandLine(
                        client_socket=client_socket,
                        ssh_script_processor=self.ssh_script_processor,
                        ssh_user=self.ssh_user,
                        ssh_pass=self.ssh_pass,
                        logger=self.logger)
                    process_name = get_command_instance.get_process_name(print_kwargs={'logger': self.logger})

                source_ip: str = client_address[0]
                source_hostname: str = socket.gethostbyaddr(source_ip)[0]
                engine_name: str = get_engine_name(domain_from_dns_server, self.engines_domains)
                dest_port: int = listening_socket_object.getsockname()[1]

                # If 'accept()' function worked well, SSL worked well, then 'client_socket' won't be empty.
                if client_socket:
                    # Get the protocol type from the socket.
                    is_tls: bool = False
                    tls_properties = ssl_base.is_tls(client_socket)
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
                            domain_from_dns_server=domain_from_dns_server,
                            forwarding_dns_service_ipv4_list___only_for_localhost=(
                                self.forwarding_dns_service_ipv4_list___only_for_localhost),
                            tls=is_tls,
                            exceptions_logger=self.exceptions_logger
                        )

                        ssl_client_socket, accept_error_message = \
                            sni_handler.wrap_socket_with_ssl_context_server_sni_extended(
                                client_socket,
                                print_kwargs={'logger': self.logger}
                            )

                        # If the 'domain_from_dns_server' is empty, it means that the 'engine_name' is not set.
                        # In this case we will set the 'engine_name' to from the SNI.
                        if engine_name == '':
                            sni_hostname: str = ssl_client_socket.server_hostname
                            if sni_hostname:
                                engine_name = get_engine_name(sni_hostname, self.engines_domains)

                        if accept_error_message:
                            # Write statistics after wrap is there was an error.
                            self.statistics_writer.write_accept_error(
                                engine=engine_name,
                                source_host=source_hostname,
                                source_ip=source_ip,
                                error_message=accept_error_message,
                                dest_port=str(dest_port),
                                host=domain_from_dns_server,
                                process_name=process_name)

                            continue

                    # Create new arguments tuple that will be passed, since client socket and process_name
                    # are gathered from SocketWrapper.
                    if ssl_client_socket:
                        # In order to use the same object, it needs to get nullified first, since the old instance
                        # will not get overwritten. Though it still will show in the memory as SSLSocket, it will not
                        # be handled as such, but as regular raw socket.
                        # noinspection PyUnusedLocal
                        client_socket = None
                        client_socket = ssl_client_socket
                    thread_args = \
                        ((client_socket, process_name, is_tls, tls_type, tls_version, domain_from_dns_server) +
                         reference_function_args)
                    # If 'pass_function_reference_to_thread' was set to 'False', execute the callable passed function
                    # as is.
                    if not pass_function_reference_to_thread:
                        before_socket_thread_worker(
                            callable_function=reference_function_name, thread_args=thread_args,
                            exceptions_logger=self.exceptions_logger)
                    # If 'pass_function_reference_to_thread' was set to 'True', execute the callable function reference
                    # in a new thread.
                    else:
                        self._send_accepted_socket_to_thread(
                            before_socket_thread_worker,
                            reference_args=(reference_function_name, thread_args, self.exceptions_logger))
                # Else, if no client_socket was opened during, accept, then print the error.
                else:
                    # Write statistics after accept.
                    self.statistics_writer.write_accept_error(
                        engine=engine_name,
                        source_host=source_hostname,
                        source_ip=source_ip,
                        error_message=accept_error_message,
                        dest_port=str(dest_port),
                        host=domain_from_dns_server,
                        process_name=process_name)
            except Exception as e:
                self.exceptions_logger.write(e)

    def _send_accepted_socket_to_thread(self, thread_function_name, reference_args=()):
        # Creating thread for each socket
        thread_current = threading.Thread(target=thread_function_name, args=(*reference_args,))
        thread_current.daemon = True
        thread_current.start()
        # Append to list of threads, so they can be "joined" later
        self.threads_list.append(thread_current)

        # 'reference_args[1][0]' is the client socket.
        client_address = base.get_source_address_from_socket(reference_args[1][0])

        self.logger.info(f"Accepted connection, thread created {client_address}. Continue listening...")


def before_socket_thread_worker(
        callable_function: callable,
        thread_args: tuple,
        exceptions_logger: loggingw.ExceptionCsvLogger = None
):
    """
    Function that will be executed before the thread is started.
    :param callable_function: callable, function that will be executed in the thread.
    :param thread_args: tuple, arguments that will be passed to the function.
    :param exceptions_logger: loggingw.ExceptionCsvLogger, logger object that will be used to log exceptions.
    :return:
    """

    try:
        callable_function(*thread_args)
    except Exception as e:
        exceptions_logger.write(e)


def get_engine_name(domain: str, engines_domains: dict):
    """
    Function that will get the engine name from the domain name.
    :param domain: string, domain name.
    :param engines_domains: dictionary, dictionary that contains the engine names and domains. Example:
        [
            {'this_is_engine_name': ['example.com', 'example.org']},
            {'this_is_engine_name2': ['example2.com', 'example2.org']}
        ]
    :return: string, engine name.
    """

    for engine_name, engine_domain_list in engines_domains.items():
        if any(engine_domain in domain for engine_domain in engine_domain_list):
            return engine_name

    return ''
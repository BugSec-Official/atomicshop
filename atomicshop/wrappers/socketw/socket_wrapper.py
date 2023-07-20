import os
import sys
import ssl
import threading
# "select" is used to call for a socket from the list of sockets, when one of the sockets gets connected
import select

from . import base, socket_client, creator, get_process, accepter
from ..certauthw.certauthw import CertAuthWrapper
from .. import pyopensslw, cryptographyw
from ...script_as_string_processor import ScriptAsStringProcessor
from ...domains import get_domain_without_first_subdomain_if_no_subdomain_return_as_is
from ... import queues


SNI_QUEUE = queues.NonBlockQueue()
PROCESS_NAME_QUEUE = queues.NonBlockQueue()


# === Socket Wrapper ===================================================================================================
class SocketWrapper:
    def __init__(
            self,
            logger=None,
            statistics_logger=None,
            config=None,
            domains_list: list = None
    ):

        self.logger = logger
        self.statistics = statistics_logger
        self.config: dict = config

        # If 'domains_list' wasn't passed, but 'config' did.
        if not domains_list and config:
            self.domains_list: list = config['certificates']['domains_all_times']
        else:
            self.domains_list: list = domains_list

        self.socket_object = None
        self.ssl_context = None

        # Server certificate file path that will be loaded into SSL Context.
        self.server_certificate_file_path: str = str()
        self.server_private_key_file_path = None

        self.config_extended: dict = dict()
        self.sni_received_dict: dict = dict()
        self.sni_execute_extended: bool = False
        self.sni_empty_destination_name: str = 'domain_is_empty_in_sni_and_dns'
        self.process_name: str = str()
        self.requested_domain_from_dns_server = None
        self.certauth_wrapper = None

        # Defining list of threads, so we can "join()" them in the end all at once.
        self.threads_list: list = list()

        # Defining listening sockets list, which will be used with "select" library in 'loop_for_incoming_sockets'.
        self.listening_sockets: list = list()

    # === Certificate functions ========================================================================================
    def initialize_certauth_create_use_ca_certificate(self):
        # Initialize CertAuthWrapper.
        if self.config['certificates']['default_server_certificate_usage']:
            server_certificate_directory = self.config['certificates']['default_server_certificate_directory']
        else:
            server_certificate_directory = self.config['certificates']['sni_server_certificates_cache_directory']

        self.certauth_wrapper = CertAuthWrapper(
            ca_certificate_name=self.config['certificates']['ca_certificate_name'],
            ca_certificate_filepath=self.config['certificates']['ca_certificate_filepath'],
            server_certificate_directory=server_certificate_directory
        )

        # Create CA certificate if it doesn't exist.
        self.certauth_wrapper.create_use_ca_certificate()

    def create_overwrite_default_server_certificate_ca_signed(self):
        self.initialize_certauth_create_use_ca_certificate()

        domain_list = self.config['certificates']['domains_all_times']
        server_certificate_file_name_no_extension = self.config['certificates']['default_server_certificate_name']

        server_certificate_file_path, default_server_certificate_san = \
            self.certauth_wrapper.create_overwrite_server_certificate_ca_signed_return_path_and_san(
                domain_list=domain_list,
                server_certificate_file_name_no_extension=server_certificate_file_name_no_extension
            )

        return server_certificate_file_path, default_server_certificate_san

    def select_server_ssl_context_certificate(self):
        # We need to nullify the variable, since we have several checks if the variable was set or not.
        self.server_certificate_file_path: str = str()

        # Creating if non-existent/overwriting default server certificate.
        # 'self.server_certificate_filepath' will be assigned there.
        if self.config['certificates']['default_server_certificate_usage']:
            self.server_certificate_file_path, default_server_certificate_san = \
                self.create_overwrite_default_server_certificate_ca_signed()

            # Check if default certificate was created.
            if self.server_certificate_file_path:
                self.logger.info(
                    f"Default Server Certificate was created / overwritten: {self.server_certificate_file_path}")
                self.logger.info(
                    f"Default Server Certificate current 'Subject Alternative Names': {default_server_certificate_san}")
            else:
                self.logger.critical(
                    f"Couldn't create / overwrite Default Server Certificate: {self.server_certificate_file_path}")
                sys.exit()

        # Assigning 'certificate_path' to 'custom_certificate_path' if usage was set.
        if self.config['certificates']['custom_server_certificate_usage']:
            self.server_certificate_file_path = self.config['certificates']['custom_server_certificate_path']
            # Since 'ssl_context.load_cert_chain' uses 'keypath' as 'None' if certificate contains private key.
            # We'd like to leave it that way and don't fetch empty string from 'config'.
            if self.config['certificates']['custom_private_key_path']:
                self.server_private_key_file_path = self.config['certificates']['custom_private_key_path']

    # === SNI Functions ================================================================================================

    def add_sni_callback_function_reference_to_ssl_context(self, sni_function_name=None):
        # If no sni function reference name was passed, then use the function in this module.
        if not sni_function_name:
            sni_function_name = self.sni_handle

        # SNI - Server Name Indication: https://en.wikipedia.org/wiki/Server_Name_Indication
        # SNI is extension to TLS protocol to tell the Server what is destination domain that the client is trying to
        # connect. The server knowing the destination domain then can present to the client the appropriate certificate.
        # "sni_callback" method: https://docs.python.org/3/library/ssl.html#ssl.SSLContext.sni_callback
        # The method calls your custom function. If there is SNI present in the TLS request from the client, then the
        # function will be called. Automatically providing 3 parameters from the system: ssl.SSLSocket, The destination
        # server name, current ssl.SSLContext object.
        # If you check the custom function it has all these variables mandatory, since this is what system provides and
        # handled by the system, if SNI is existent.
        # The function is actually called at "accept()" method of the "ssl.SSLSocket"
        # This needs to be set only once on the listening socket
        self.ssl_context.sni_callback = sni_function_name

    # Server Name Indication (SNI) is an extension to the Transport Layer Security (TLS) computer networking protocol.
    # Function to handle server's SSLContext's SNI callback function.
    # This is actually called first during "accept()" method of the "ssl.SSLSocket" then comes accept itself.
    # This happens in 'ssl.py' module in 'self._sslobj.do_handshake()' function.
    # noinspection PyUnboundLocalVariable
    def sni_handle(self,
                   sni_ssl_socket: ssl.SSLSocket,
                   sni_destination_name: str,
                   sni_ssl_context: ssl.SSLContext):

        # Get the variables from sni.
        self.sni_received_dict = {
            'ssl_socket': sni_ssl_socket,
            'destination_name': sni_destination_name,
            'ssl_context': sni_ssl_context
        }

        # If 'sni_execute_extended' was set to True.
        if self.sni_execute_extended:
            self.sni_extended()
        # Just set the server_hostname in current socket.
        else:
            self.sni_received_dict['ssl_socket'].server_hostname = sni_destination_name

    def sni_extended(self):
        # Set 'server_hostname' for the socket.
        self.sni_set_socket_server_hostname()

        # SSH Remote / LOCALHOST script execution to identify process section
        # If 'config.tcp['get_process_name']' was set to True in 'config.ini', then this will be executed.
        if self.config['sni']['get_process_name']:
            self.sni_get_process_name()

        # If 'sni_default_server_certificates_addons' was set to 'True' in the 'config.ini'.
        # This section will add all the new domains that hit the server to default certificate SAN with wildcard.
        if self.config['sni']['default_server_certificate_addons']:
            self.sni_add_domain_to_default_server_certificate()

        # If SNI server certificate creation was set to 'True', we'll create certificate for each incoming domain if
        # non-existent in certificates cache folder.
        if self.config['certificates']['sni_create_server_certificate_for_each_domain']:
            self.create_use_sni_server_certificate_ca_signed()

    def sni_set_socket_server_hostname(self):
        # Try on general settings in the SNI function.
        try:
            # Check if SNI was passed.
            if self.sni_received_dict['destination_name']:
                service_name_from_sni = self.sni_received_dict['destination_name']
            # If no SNI was passed.
            else:
                # If DNS server is enabled we'll get the domain from dns server.
                if self.requested_domain_from_dns_server.queue:
                    service_name_from_sni = self.requested_domain_from_dns_server.queue
                    self.logger.info(f"SNI Handler: No SNI was passed, using domain from DNS Server: "
                                     f"{service_name_from_sni}")
                # If DNS server is disabled, the domain from dns server will be empty.
                else:
                    service_name_from_sni = self.sni_empty_destination_name
                    self.logger.info(f"SNI Handler: No SNI was passed, No domain passed from DNS Server. "
                                     f"Filling the service name with: [{service_name_from_sni}]")

            # Setting "server_hostname" as a domain.
            SNI_QUEUE.queue = self.sni_received_dict['ssl_socket'].server_hostname = service_name_from_sni
            self.logger.info(
                f"SNI Handler: port {self.sni_received_dict['ssl_socket'].getsockname()[1]}: "
                f"Incoming connection for [{self.sni_received_dict['ssl_socket'].server_hostname}]")
        except Exception as exception_object:
            self.logger.error_exception_oneliner(
                f"SNI Handler: Undocumented exception general settings section: "
                f"{exception_object}")
            pass

    def sni_get_process_name(self):
        # Get client ip and the source port.
        client_ip, source_port = base.get_source_address_from_socket(self.sni_received_dict['ssl_socket'])

        # Put source port variable inside the string script.
        updated_script_string = \
            self.config_extended['ssh']['script_processor'].put_variable_into_script_string(
                source_port, logger=self.logger)

        process_name = get_process.get_process_commandline(
            client_ip=client_ip,
            username=self.config['ssh']['user'],
            password=self.config['ssh']['pass'],
            script_string=updated_script_string,
            logger=self.logger)

        self.process_name = process_name
        PROCESS_NAME_QUEUE.queue = process_name

        return process_name

    def sni_add_domain_to_default_server_certificate(self):
        # Check if incoming domain is already in the parent domains of 'domains_all_times' list.
        if not any(x in self.sni_received_dict['ssl_socket'].server_hostname for x in
                   self.config['certificates']['domains_all_times']):
            self.logger.info(f"SNI Handler: Current domain is not in known domains list. Adding.")
            # In the past was using 'certauth' to extract tlds, but it works only in online mode, so rewrote
            # the function to disable online fetching of TLD snapshot.
            # Initialize 'certauth' object.
            # certificate_object = CertificateAuthority(certificate_ca_name, certificate_ca_filepath)
            # Extract parent domain from the current SNI domain.
            # parent_domain = certificate_object.get_wildcard_domain(service_name_from_sni)

            # Extract parent domain from the current SNI domain.
            parent_domain = get_domain_without_first_subdomain_if_no_subdomain_return_as_is(
                self.sni_received_dict['ssl_socket'].server_hostname)
            # Add the parent domain to the known domains list.
            self.config['certificates']['domains_all_times'].append(parent_domain)

            default_server_certificate_path, subject_alternate_names = \
                self.create_overwrite_default_server_certificate_ca_signed()
            if default_server_certificate_path:
                self.logger.info(
                    f"SNI Handler: Default Server Certificate was created / overwritten: "
                    f"{default_server_certificate_path}")
                self.logger.info(
                    f"SNI Handler: Server Certificate current 'Subject Alternative Names': "
                    f"{subject_alternate_names}")

                # Since new default certificate was created we need to create new SSLContext and add the certificate.
                # You need to build new context and exchange the context that being inherited from the main socket,
                # or else the context will receive previous certificate each time.
                self.sni_received_dict['ssl_socket'].context = \
                    creator.create_server_ssl_context___load_certificate_and_key(default_server_certificate_path, None)
            else:
                self.logger.critical(
                    f"Couldn't create / overwrite Default Server Certificate: {default_server_certificate_path}")
                sys.exit()

    def create_use_sni_server_certificate_ca_signed(self):
        # === Connect to the domain and get the certificate. ===========================================================
        certificate_from_socket_x509 = None
        if self.config['certificates']['sni_get_server_certificate_from_server_socket']:
            # Generate PEM certificate file path string for downloaded certificates. Signed certificates will go to the
            # 'certs' folder.
            certificate_from_socket_file_path: str = \
                self.config['certificates']['sni_server_certificate_from_server_socket_download_directory'] + \
                os.sep + self.sni_received_dict['destination_name'] + ".pem"
            # Get client ip.
            client_ip = base.get_source_address_from_socket(self.sni_received_dict['ssl_socket'])[0]

            # If we're on localhost, then use external services list in order to resolve the domain:
            if client_ip == "127.0.0.1":
                service_client = socket_client.SocketClient(
                    service_name=self.sni_received_dict['destination_name'],
                    service_port=base.get_destination_address_from_socket(self.sni_received_dict['ssl_socket'])[1],
                    dns_servers_list=self.config['tcp']['forwarding_dns_service_ipv4_list___only_for_localhost'])
            # If we're not on localhost, then connect to domain directly.
            else:
                service_client = socket_client.SocketClient(
                    service_name=self.sni_received_dict['destination_name'],
                    service_port=base.get_destination_address_from_socket(self.sni_received_dict['ssl_socket'])[1])

            # Get certificate from socket and convert to X509 cryptography module object.
            certificate_from_socket_x509_cryptography_object = service_client.get_certificate_from_server(
                save_as_file=True, cert_file_path=certificate_from_socket_file_path, cert_output_type='cryptography'
            )

            # skip_extensions = ['1.3.6.1.5.5.7.3.2', '2.5.29.31', '1.3.6.1.5.5.7.1.1']

            # If certificate was downloaded successfully, then remove extensions if they were provided.
            # If certificate was downloaded successfully and no extensions to skip were provided, then use it as is.
            if certificate_from_socket_x509_cryptography_object and self.config['skip_extensions']:
                # Copy extensions from old certificate to new certificate, without specified extensions.
                certificate_from_socket_x509_cryptography_object, _ = \
                    cryptographyw.copy_extensions_from_old_cert_to_new_cert(
                        certificate_from_socket_x509_cryptography_object,
                        skip_extensions=self.config['skip_extensions'],
                        print_kwargs={'logger': self.logger}
                    )

            # If certificate was downloaded successfully, then convert it to pyopenssl object.
            if certificate_from_socket_x509_cryptography_object:
                # Convert X509 cryptography module object to pyopenssl, since certauth uses pyopenssl.
                certificate_from_socket_x509 = \
                    pyopensslw.convert_cryptography_object_to_pyopenssl(certificate_from_socket_x509_cryptography_object)

        # === EOF Get certificate from the domain. =====================================================================

        # If CertAuthWrapper wasn't initialized yet, it means that CA wasn't created/loaded yet.
        if not self.certauth_wrapper:
            self.initialize_certauth_create_use_ca_certificate()
        # try:
        # Create if non-existent / read existing server certificate.
        sni_server_certificate_file_path = self.certauth_wrapper.create_read_server_certificate_ca_signed(
            self.sni_received_dict['destination_name'], certificate_from_socket_x509)
        self.logger.info(f"SNI Handler: port "
                         f"{base.get_destination_address_from_socket(self.sni_received_dict['ssl_socket'])[1]}: "
                         f"Using certificate: {sni_server_certificate_file_path}")
        # except Exception as e:
        #     message = \
        #         f"SNI Handler: Undocumented exception while creating / using certificate for a domain: {e}"
        #     print_api(
        #         message, error_type=True, logger_method="critical", traceback_string=True, oneline=True,
        #         logger=self.logger)
        #     pass

        # try:
        # You need to build new context and exchange the context that being inherited from the main socket,
        # or else the context will receive previous certificate each time.
        self.sni_received_dict['ssl_socket'].context = \
            creator.create_server_ssl_context___load_certificate_and_key(sni_server_certificate_file_path, None)
        # except Exception as e:
        #     message = \
        #         f"SNI Handler: Undocumented exception while creating and assigning new SSLContext: {e}"
        #     print_api(
        #         message, error_type=True, logger_method="critical", traceback_string=True, oneline=True,
        #         logger=self.logger)
        #     pass

    # Creating listening sockets.
    def create_socket_ipv4_tcp_ssl_sni_extended(self, ip_address: str, port: int):
        self.sni_execute_extended = True

        if self.config['sni']['get_process_name']:
            self.config_extended = {
                'ssh': {
                    'script_processor':
                        ScriptAsStringProcessor().read_script_to_string(self.config['ssh']['script_to_execute'])
                }
            }

        self.socket_object = creator.create_socket_ipv4_tcp()
        creator.add_reusable_address_option(self.socket_object)
        self.ssl_context = creator.create_ssl_context_for_server()
        self.add_sni_callback_function_reference_to_ssl_context()
        self.select_server_ssl_context_certificate()

        # If the user chose 'sni_create_server_certificate_for_each_domain = 1' in the configuration file,
        # it means that 'self.server_certificate_file_path' will be empty, which is OK, since we'll inject
        # dynamically created certificate from certs folder through SNI.
        if self.server_certificate_file_path:
            creator.load_certificate_and_key_into_server_ssl_context(
                self.ssl_context, self.server_certificate_file_path, self.server_private_key_file_path,
                logger=self.logger)

        self.socket_object = creator.wrap_socket_with_ssl_context_server(self.socket_object, self.ssl_context)
        creator.bind_socket_with_ip_port(self.socket_object, ip_address, port, logger=self.logger)
        creator.set_listen_on_socket(self.socket_object, logger=self.logger)

        return self.socket_object

    def create_tcp_listening_socket_list(self, overwrite_list: bool = False):
        # If 'overwrite_list' was set to 'True', we will create new list. The default is 'False', since it is meant to`
        # add new sockets to already existing ones.
        if overwrite_list:
            self.listening_sockets = list()

        # Creating a socket for each port in the list set in configuration file
        for port in self.config['tcp']['listening_port_list']:
            socket_by_port = self.create_socket_ipv4_tcp_ssl_sni_extended(
                self.config['tcp']['listening_interface'], port)

            self.listening_sockets.append(socket_by_port)

    def send_accepted_socket_to_thread(self, thread_function_name, reference_args=()):
        # Creating thread for each socket
        thread_current = threading.Thread(target=thread_function_name, args=(*reference_args,))
        # Append to list of threads, so they can be "joined" later
        self.threads_list.append(thread_current)
        # Start the thread
        thread_current.start()

        # 'reference_args[0]' is the client socket.
        client_address = base.get_source_address_from_socket(reference_args[0])

        self.logger.info(f"Accepted connection, thread created {client_address}. Continue listening...")

    def loop_for_incoming_sockets(
            self, function_reference, listening_socket_list: list = None,
            pass_function_reference_to_thread: bool = True, reference_args=(), *args, **kwargs):
        """
        Loop to wait for new connections, accept them and send to new threads.
        The boolean variable was declared True in the beginning of the script and will be set to False if the process
        will be killed or closed.

        :param function_reference: callable, function reference that you want to execute when client
            socket received by 'accept()' and connection been made.
        :param listening_socket_list: list, of sockets that you want to listen on.
        :param pass_function_reference_to_thread: boolean, that sets if 'function_reference' will be
            executed as is, or passed to thread. 'function_reference' can include passing to a thread,
            but you don't have to use it, since SocketWrapper can do it for you.
        :param reference_args: tuple, that will be passed to 'function_reference' when it will be called.
        :param kwargs:
        :return:
        """

        # If 'listening_socket_list' wasn't specified and 'self.listening_sockets' is not empty.
        if not listening_socket_list and self.listening_sockets:
            # Then assign 'self.listening_sockets'.
            listening_socket_list = self.listening_sockets

        # Socket accept infinite loop run variable. When the process is closed, the loop will break and the threads will
        # be joined and garbage collection cleaned if there is any
        socket_infinite_loop_run: bool = True
        while socket_infinite_loop_run:
            # Using "select.select" which is currently the only API function that works on all operating system types
            # Windows / Linux / BSD.
            # To accept connection, we don't need "writable" and "exceptional", since "readable" holds the currently
            # connected socket.
            readable, writable, exceptional = select.select(listening_socket_list, [], [])
            listening_socket_object = readable[0]

            # Get the domain queue. Tried using "Queue.Queue" object, but it stomped the SSL Sockets
            # from accepting connections.
            if self.requested_domain_from_dns_server.queue:
                self.logger.info(f"Requested domain from DNS Server: {self.requested_domain_from_dns_server.queue}")

            # Wait from any connection on "accept()".
            # 'client_socket' is socket or ssl socket, 'client_address' is a tuple (ip_address, port).
            client_socket, client_address = accepter.accept_connection(
                listening_socket_object, statistics=self.statistics, sni_queue=SNI_QUEUE,
                process_name_queue=PROCESS_NAME_QUEUE, logger=self.logger)
            # If 'accept()' function worked well, SSL worked well, then 'client_socket' won't be empty.
            if client_socket:
                # Create new arguments tuple that will be passed, since client socket and process_name
                # are gathered from SocketWrapper.
                thread_args = (client_socket, self.process_name) + reference_args
                # If 'pass_function_reference_to_thread' was set to 'False', execute the callable passed function
                # as is.
                if not pass_function_reference_to_thread:
                    function_reference(thread_args, *args, **kwargs)
                # If 'pass_function_reference_to_thread' was set to 'True', execute the callable function reference
                # in a new thread.
                else:
                    self.send_accepted_socket_to_thread(function_reference, thread_args)

# v1.1.1 - 21.03.2023 13:50
import sys
import datetime
import socket
import ssl
import threading
# "select" is used to call for a socket from the list of sockets, when one of the sockets gets connected
import select
# Needed to redirect output from console to logger on LOCALHOST process command line harvesting.
import io
from contextlib import redirect_stdout

from ..script_as_string_processor import ScriptAsStringProcessor
from ..domains import get_domain_without_first_subdomain_if_no_subdomain_return_as_is
from ..wrappers.certauthw import CertAuthWrapper
from ..ssh_remote import SSHRemote


# === Functions ========================================================================================================
def get_process_commandline(client_ip: str, username: str, password: str, script_string: str, logger):
    import psutil

    # Defining locals.
    process_name = None
    execution_output = None
    execution_error = None

    # Checking if we're on localhost. If not, we'll execute SSH connection to get calling process name.
    if client_ip != "127.0.0.1":
        # Tried using paramiko SSH concurrently within threads, but with bigger loads it just breaks.
        # So, better using it separately for each thread.

        logger.info(f"Initializing SSH connection to [{client_ip}]")
        # Initializing SSHRemote class.
        current_ssh_client = SSHRemote(ip_address=client_ip,
                                       username=username,
                                       password=password)

        execution_output, execution_error = current_ssh_client.connect_get_client_commandline(script_string)
    # Else, if we're on localhost, then execute the script directly without SSH.
    else:
        logger.info("Executing LOCALHOST command to get the calling process.")
        # Getting the redirection from console print, since that what the 'script_string' does.
        with io.StringIO() as buffer, redirect_stdout(buffer):
            # Executing the script with print to console.
            try:
                exec(script_string)
            except ModuleNotFoundError as function_exception_object:
                execution_error = f"Module not installed: {function_exception_object}"
                logger.error_exception_oneliner(execution_error)
                pass
            except psutil.AccessDenied:
                execution_error = f"Access Denied for 'psutil' to read system process command line. " \
                                  f"Run script with Admin Rights."
                logger.error_exception_oneliner(execution_error)
                pass
            except Exception as function_exception_object:
                execution_error = function_exception_object
                logger.error_exception_oneliner(
                    "There was undocumented exception in localhost script execution.")
                pass

            if not execution_error:
                # Reading the buffer.
                execution_output = buffer.getvalue()

    # This section is generic for both remote SSH and localhost executions of the script.
    process_name = get_commandline_and_error(execution_output, execution_error, logger)

    return process_name


def get_commandline_and_error(execution_output, execution_error, logger):
    # Defining locals.
    process_name = None

    # If there was known error on localhost / known error on remote or any kind of error on remote, it was
    # already logged, so we'll just put the error into 'process_name'.
    if execution_error:
        process_name = execution_error
        logger.error(f"Error During Command Execution: {process_name}")
    # If there wasn't any error of above types, then we can put the output from either local or remote script
    # execution into 'process_name' and log it / output to console.
    else:
        # If the output that was returned is not empty.
        if execution_output:
            # Replacing '\r\n' escape lines with string, so that the line will not be escaped in logs.
            if '\r\n' in execution_output:
                execution_output = execution_output.replace('\r\n', '')
            elif '\n' in execution_output:
                execution_output = execution_output.replace('\n', '')

            process_name = execution_output
            logger.info(f"Client Process Command Line: {process_name}")
        # Else if the script output came back empty.
        else:
            process_name = "Client Process Command Line came back empty after script execution."
            logger.error(process_name)

    return process_name


def create_ssl_context_for_server():
    # Creating context with SSL certificate and the private key before the socket
    # https://docs.python.org/3/library/ssl.html
    # Creating context for SSL wrapper, specifying "PROTOCOL_TLS_SERVER" will pick the best TLS version protocol for
    # the server.
    return ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)


def create_server_ssl_context_and_load_certificate_and_key(certificate_file_path: str, key_file_path):
    # Initialize SocketWrapper.
    socket_wrapper = SocketWrapper()
    # Create and set ssl context for server.
    socket_wrapper.set_new_server_ssl_context()
    # Load certificate into context.
    socket_wrapper.load_certificate_and_key_into_server_ssl_context(certificate_file_path, key_file_path)
    # Return ssl context only.
    return socket_wrapper.ssl_context


# Return destination IP and port.
def get_destination_address_from_socket(socket_object):
    # return ip_address, port
    return socket_object.getsockname()[0], socket_object.getsockname()[1]


# Return source IP and port.
def get_source_address_from_socket(socket_object):
    # return ip_address, port
    return socket_object.getpeername()[0], socket_object.getpeername()[1]


def get_source_destination(socket_object):
    return get_source_address_from_socket(socket_object), get_destination_address_from_socket(socket_object)


class DomainQueue:
    """
    Class that is responsible for storing current requested domain.
    Since it is passed between classes as an instance, it will be the same instance between classes and threads
    as long as it is used in the same process.
    """
    def __init__(self):
        self.queue: str = str()


class SniQueue:
    """
    Class that is responsible for storing current domain that was set during extended sni.
    Since it is passed between classes as an instance, it will be the same instance between classes and threads
    as long as it is used in the same process.
    """
    def __init__(self):
        self.queue: str = str()


SNI_QUEUE = SniQueue()


# === Socket Wrapper ===================================================================================================
class SocketWrapper:
    def __init__(
            self, socket_object=None, ssl_context=None, logger=None, statistics_logger=None, config=None,
            domains_list: list = None):
        self.socket_object = socket_object
        self.ssl_context = ssl_context

        # Server certificate file path that will be loaded into SSL Context.
        self.server_certificate_file_path: str = str()
        self.server_private_key_file_path = None

        self.config: dict = config
        self.config_extended: dict = dict()

        # If 'sni_extended_args_dict' was passed, we'll update the default dict with new values.
        # This makes it useful if the dict passed is partial, since we will still have default values.
        # if sni_extended_args_dict:
        #     self.sni_extended_args_dict.update(sni_extended_args_dict)

        self.sni_received_dict: dict = dict()
        self.sni_execute_extended: bool = False
        self.sni_empty_destination_name: str = 'domain_is_empty_in_sni_and_dns'
        self.process_name: str = str()

        # self.requested_domain_from_dns_server: str = str()
        self.requested_domain_from_dns_server = None

        # If 'domains_list' wasn't passed, but 'config' did.
        if not domains_list and config:
            self.domains_list: list = config['certificates']['domains_all_times']
        else:
            self.domains_list: list = domains_list

        self.certauth_wrapper = None

        self.logger = logger
        self.statistics = statistics_logger

        # Defining list of threads, so we can "join()" them in the end all at once.
        self.threads_list: list = list()

        # Defining listening sockets list, which will be used with "select" library in 'loop_for_incoming_sockets'.
        self.listening_sockets: list = list()

        # self.select_server_ssl_context_certificate()

    # === Create socket presets ========================================================================================

    def create_socket_ipv4_tcp(self):
        # When using 'with' statement, no need to use "socket.close()" method to disconnect when finished
        # AF_INET - Socket family of IPv4
        # SOCK_STREAM - Socket type of TCP
        self.socket_object = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # === Basic functions ==============================================================================================

    def add_reusable_address_option(self):
        # "setsockopt" is a method that can add options to the socket. Not needed for regular connection,
        # but for some types of protocols that come after that.
        # SOL_SOCKET - the "level", constant that contains the "SP_REUSEADDR"
        # SO_REUSEADDR - permit reuse of local addresses for this socket. If you enable this option, you can actually
        # have two sockets with the same Internet port number. Needed for protocols that force you to use the same port.
        # 1 - Sets this to true
        # For more options of this constant:
        # https://www.gnu.org/software/libc/manual/html_node/Socket_002dLevel-Options.html#Socket_002dLevel-Options
        self.socket_object.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def set_socket_timeout(self, seconds: int = 1):
        # Setting timeout on the socket before "accept()" drastically slows down connections.
        self.socket_object.settimeout(seconds)

    def bind_socket_with_ip_port(self, ip_address: str, port: int):
        # "bind()" the socket object to the server host address and the listening port.
        # IPv4 address and port are required for the "AF_INET" socket family (can be IPv4, hostname, empty). On empty
        # string, the server will accept connections on all available IPv4 interfaces.
        # You need to bind only the main listening socket, no need to throw it to threads
        # Bind will be only set for a server and not for the client. Bind assigns the port to the application that uses
        # it, since it is always needs to be listening for new connections, unlike client that only sends the request
        # and doesn't listen to the specific port.
        try:
            self.socket_object.bind((ip_address, port))
        # WindowsError is inherited from OSError. It is available when OSError has "WinError" line in it.
        # Off course under linux it will be different.
        except WindowsError as exception_object:
            # Check if the specific "WinError" is "10049"
            # Also, "sys.exc_info()[1].winerror" can be used, but less specific to WindowsError in this case
            # if sys.exc_info()[1].winerror == 10049:
            if exception_object.winerror == 10049:
                self.logger.critical_exception(f"Couldn't bind to interface {ip_address} on port"
                                               f" {port}. Check the address of the interface")
                sys.exit()
            # If it's not the specific WinError, then raise the exception regularly anyway
            else:
                raise

    def set_listen_on_socket(self):
        # You need to listen to the main socket once.
        # The number given within 'listen()' is the size of the backlog queue - number of pending requests.
        # Leaving empty will choose default.
        # Specifying number higher than the OS is supporting will truncate to that number. Some linux distributions
        # support maximum of 128 'backlog' sockets. Specifying number higher than 128 will truncate to 128 any way.
        # To determine the maximum listening sockets, you may use the 'socket' library and 'SOMAXCONN' parameter
        # from it.
        self.socket_object.listen(socket.SOMAXCONN)
        ip_address, port = self.get_destination_address()
        self.logger.info(f"Listening for new connections on: {ip_address}:{port}")

    # Function to accept new connections
    def accept_connection(self, socket_object, statistics, **kwargs):
        function_client_socket = None
        function_client_address: tuple = tuple()

        if 'logger' in kwargs.keys():
            logger = kwargs['logger']

        try:
            # "accept()" bloc script I/O calls until receives network connection. When client connects "accept()"
            # returns client socket and client address. Non-blocking mode is supported with "setblocking()", but you
            # need to change your application accordingly to handle this.
            # The client socket will contain the address and the port.
            # Since the client socket is thrown each time to a thread function, it can be overwritten in the main loop
            # and thrown to the function again. Accept creates new socket each time it is being called on the main
            # socket.
            function_client_socket, function_client_address = socket_object.accept()
            # "accept()" method of the "ssl.SSLSocket" object returns another "ssl.SSLSocket" object and not the
            # regular socket
            function_client_socket: ssl.SSLSocket
            function_client_address: tuple
        # Each exception that calls 'service_name_from_sni' variables has a try on calling that variable.
        # If it is non-existent, then logger function that doesn't have this variable printed will be used.
        # After that second exception will be "pass"-ed. This is an exception inside an exception handling.
        # Looks like was introduced in Python 3 in PEP 3134.
        except ConnectionAbortedError:
            message = f"Socket Accept: {SNI_QUEUE.queue}:{socket_object.getsockname()[1]}: " \
                      f"* Established connection was aborted by software on the host..."
            logger.error_exception_oneliner(message)
            pass
        except ConnectionResetError:
            message = f"Socket Accept: {SNI_QUEUE.queue}:{socket_object.getsockname()[1]}: " \
                      f"* An existing connection was forcibly closed by the remote host..."
            logger.error_exception_oneliner(message)
            pass
        except ssl.SSLEOFError:
            # A subclass of SSLError raised when the SSL connection has been terminated abruptly. Generally, you
            # shouldn't try to reuse the underlying transport when this error is encountered.
            # https://docs.python.org/3/library/ssl.html#ssl.SSLEOFError
            # Nothing to do with it.

            message = "* SSL EOF Error on accept. Could be connection aborted in the middle..."
            try:
                message = f"Socket Accept: {SNI_QUEUE.queue}:{socket_object.getsockname()[1]}: {message}"
                logger.error_exception_oneliner(message)
            except Exception:
                message = f"Socket Accept: port {socket_object.getsockname()[1]}: {message}"
                logger.error_exception_oneliner(message)
                pass
            pass
        except ssl.SSLError as exception_object:
            # Getting the exact reason of "ssl.SSLError"
            if exception_object.reason == "HTTP_REQUEST":
                message = f"Socket Accept: HTTP Request on SSL Socket: {get_source_destination(socket_object)}"
                logger.error_exception_oneliner(message)
            elif exception_object.reason == "TSV1_ALERT_UNKNOWN_CA":
                message = f"Socket Accept: Check certificate on the client for CA " \
                          f"{get_source_destination(socket_object)}"
                logger.error_exception_oneliner(message)
            else:
                # Not all requests have the server name passed through Client Hello.
                # If it is not passed an error of undefined variable will be raised.
                # So, we'll check if the variable as a string is in the "locals()" variable pool.
                # Alternatively we can check if the variable is in the "global()" and then pull it from there.

                message = "SSLError on accept. For more info check the OpenSSL module documentation..."
                try:
                    message = f"Socket Accept: {SNI_QUEUE.queue}:{socket_object.getsockname()[1]}: {message}"
                    logger.error_exception_oneliner(message)
                except Exception:
                    message = f"Socket Accept: port {socket_object.getsockname()[1]}: {message}"
                    logger.error_exception_oneliner(message)
                pass
            pass
        except FileNotFoundError:
            message = "'SSLSocket.accept()' crashed: 'FileNotFoundError'. Some problem with SSL during Handshake - " \
                      "Could be certificate, client, or server."
            try:
                message = f"Socket Accept: {SNI_QUEUE.queue}:{socket_object.getsockname()[1]}: {message}"
                logger.error_exception_oneliner(message)
            except Exception:
                message = f"Socket Accept: port {socket_object.getsockname()[1]}: {message}"
                logger.error_exception_oneliner(message)
                pass
            pass
        # After all executions tested, this is what will be executed.
        finally:
            # If 'message' is not defined, it means there was no execution and there is no need for statistics.
            try:
                statistics_dict = {
                    'request_time_sent': datetime.datetime.now(),
                    'host': SNI_QUEUE.queue,
                    'error': message
                }

                statistics.info(
                    f"{statistics_dict['request_time_sent']},"
                    f"{statistics_dict['host']},"
                    f",,,,,,"
                    f"\"{self.process_name}\","
                    f"{statistics_dict['error']}"
                )
            except UnboundLocalError:
                pass

            # Exception testing
            # logger.error(f"Some SSL Test exception, {traceback_oneliner()}")

        return function_client_socket, function_client_address

    # === SSL Functions ================================================================================================

    def set_new_server_ssl_context(self):
        self.ssl_context: ssl.SSLContext = create_ssl_context_for_server()

    def load_certificate_and_key_into_server_ssl_context(self, certificate_file_path: str = str(), key_file_path=None):
        if not certificate_file_path:
            certificate_file_path = self.server_certificate_file_path

        if not key_file_path:
            key_file_path = self.server_private_key_file_path

        # If the certificate contains both the key and the certificate in one file,
        # "keyfile" parameter can be "None".
        try:
            self.ssl_context.load_cert_chain(certfile=certificate_file_path, keyfile=key_file_path)
        except ssl.SSLError as exception_object:
            if 'PEM' in str(exception_object):
                self.logger.critical(
                    f'Custom Certificate Problem with either certificate or key.\n'
                    f'Make sure that both are in ".PEM" format\n'
                    f"Or your certificate contains the key if you didn't specify it.\n"
                    f'{exception_object}')
            sys.exit()

    def wrap_socket_with_ssl_context_server(self):
        # Wrapping the server socket with SSL context. This should happen right after setting up the raw socket.
        self.socket_object: ssl.SSLSocket = self.ssl_context.wrap_socket(self.socket_object, server_side=True)

    # === Certificate functions ========================================================================================
    def initialize_certauth_create_use_ca_certificate(self):
        # Initialize CertAuthWrapper.
        self.certauth_wrapper = CertAuthWrapper(
            ca_certificate_name=self.config['certificates']['ca_certificate_name'],
            ca_certificate_filepath=self.config['certificates']['ca_certificate_filepath'],
            server_certificate_directory=self.config['certificates']['default_server_certificate_directory'],
        )

    def create_overwrite_default_server_certificate_ca_signed(self):
        self.initialize_certauth_create_use_ca_certificate()

        server_certificate_file_path, default_server_certificate_san = \
            self.certauth_wrapper.create_overwrite_server_certificate_ca_signed_return_path_and_san(
                domain_list=self.config['certificates']['domains_all_times'],
                server_certificate_file_name_no_extension=
                self.config['certificates']['default_server_certificate_name'],
                logger=self.logger
            )

        return server_certificate_file_path, default_server_certificate_san

    def select_server_ssl_context_certificate(self):
        # We need to nullify the variable, since we have several checks if the variable was set or not.
        self.server_certificate_file_path = str()

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
        if self.config['sni']['default_server_certificate_sni_addons']:
            self.sni_add_domain_to_default_server_certificate()

        # If SNI server certificate creation was set to 'True', we'll create certificate for each incoming domain if
        # non-existent in certificates cache folder.
        if self.config['certificates']['sni_create_server_certificate_for_each_domain']:
            self.create_use_sni_server_certificate_ca_signed()

    def read_script_string_for_ssh(self):
        if self.config['sni']['get_process_name']:
            self.config_extended = {
                'ssh': {
                    'script_processor': ScriptAsStringProcessor()
                }
            }
            self.config_extended['ssh']['script_processor'].read_script_to_string(
                self.config['ssh']['script_to_execute'])

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
        client_ip, source_port = SocketWrapper(socket_object=self.sni_received_dict['ssl_socket']).get_source_address()

        # Put source port variable inside the string script.
        updated_script_string = \
            self.config_extended['ssh']['script_processor'].put_variable_into_script_string(
                source_port, logger=self.logger)

        process_name = get_process_commandline(
            client_ip=client_ip,
            username=self.config['ssh']['user'],
            password=self.config['ssh']['pass'],
            script_string=updated_script_string,
            logger=self.logger)

        self.process_name = process_name

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
                self.sni_received_dict['ssl_socket'].context = create_server_ssl_context_and_load_certificate_and_key(
                    default_server_certificate_path, None)
            else:
                self.logger.critical(
                    f"Couldn't create / overwrite Default Server Certificate: {default_server_certificate_path}")
                sys.exit()

    def create_use_sni_server_certificate_ca_signed(self):
        # If CertAuthWrapper wasn't initialized yet, it means that CA wasn't created/loaded yet..
        if not self.certauth_wrapper:
            self.initialize_certauth_create_use_ca_certificate()

        try:
            # Create if non-existent / read existing server certificate.
            sni_server_certificate_file_path = self.certauth_wrapper.create_read_server_certificate_ca_signed(
                self.sni_received_dict['destination_name'])
            self.logger.info(f"SNI Handler: port "
                             f"{get_destination_address_from_socket(self.sni_received_dict['ssl_socket'])[1]}: "
                             f"Using certificate: {sni_server_certificate_file_path}")
        except Exception as exception_object:
            self.logger.error_exception_oneliner(f"SNI Handler: Undocumented exception while creating / using "
                                                 f"certificate for a domain: {exception_object}")
            pass

        try:
            # You need to build new context and exchange the context that being inherited from the main socket,
            # or else the context will receive previous certificate each time.
            self.sni_received_dict['ssl_socket'].context = create_server_ssl_context_and_load_certificate_and_key(
                sni_server_certificate_file_path, None)
        except Exception as exception_object:
            self.logger.error_exception_oneliner(f"SNI Handler: Undocumented exception while creating and "
                                                 f"assigning new SSLContext: {exception_object}")
            pass

    # Creating listening sockets.
    def create_socket_ipv4_tcp_ssl_sni_extended(self, ip_address: str, port: int):
        # Catching all the socket exceptions until accept
        try:
            self.sni_execute_extended = True
            self.read_script_string_for_ssh()

            self.create_socket_ipv4_tcp()
            self.add_reusable_address_option()
            self.set_new_server_ssl_context()
            self.add_sni_callback_function_reference_to_ssl_context()
            self.select_server_ssl_context_certificate()
            self.load_certificate_and_key_into_server_ssl_context()
            self.wrap_socket_with_ssl_context_server()
            self.bind_socket_with_ip_port(ip_address, port)
            self.set_listen_on_socket()
        except Exception:
            self.logger.critical_exception("General Exception from the MAIN thread on socket creation.")
            sys.exit()

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

    # Return destination IP and port.
    def get_destination_address(self):
        # return ip_address, port.
        return get_destination_address_from_socket(self.socket_object)

    def get_source_address(self):
        # return ip_address, port.
        return get_source_address_from_socket(self.socket_object)

    def send_accepted_socket_to_thread(self, thread_function_name, reference_args=()):
        # Creating thread for each socket
        thread_current = threading.Thread(target=thread_function_name, args=(*reference_args,))
        # Append to list of threads, so they can be "joined" later
        self.threads_list.append(thread_current)
        # Start the thread
        thread_current.start()

        # 'reference_args[0]' is the client socket.
        client_address = get_source_address_from_socket(reference_args[0])

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
            client_socket, client_address = self.accept_connection(
                listening_socket_object, statistics=self.statistics, logger=self.logger)
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

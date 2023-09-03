import threading
import select

from . import base, creator, get_process, accepter, statistics_csv, ssl_base
from ...script_as_string_processor import ScriptAsStringProcessor
from ... import queues
from ...print_api import print_api


SNI_QUEUE = queues.NonBlockQueue()


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

        # Server certificate file path that will be loaded into SSL Context.
        self.server_certificate_file_path: str = str()
        self.server_private_key_file_path = None

        self.sni_received_dict: dict = dict()
        self.sni_execute_extended: bool = False
        self.requested_domain_from_dns_server = None
        self.certauth_wrapper = None

        # Defining list of threads, so we can "join()" them in the end all at once.
        self.threads_list: list = list()

        # Defining listening sockets list, which will be used with "select" library in 'loop_for_incoming_sockets'.
        self.listening_sockets: list = list()

        # Defining 'ssh_script_processor' variable, which will be used to process SSH scripts.
        self.ssh_script_processor = None
        if self.config['ssh']['get_process_name']:
            self.ssh_script_processor = \
                ScriptAsStringProcessor().read_script_to_string(self.config['ssh']['script_to_execute'])

    # Creating listening sockets.
    def create_socket_ipv4_tcp(self, ip_address: str, port: int):
        self.sni_execute_extended = True
        self.socket_object = creator.create_socket_ipv4_tcp()
        creator.add_reusable_address_option(self.socket_object)
        creator.bind_socket_with_ip_port(self.socket_object, ip_address, port, logger=self.logger)
        creator.set_listen_on_socket(self.socket_object, logger=self.logger)

        # self.socket_object, accept_error_message = creator.wrap_socket_with_ssl_context_server_sni_extended(
        #     self.socket_object, config=self.config, print_kwargs={'logger': self.logger})

        return self.socket_object

    def create_tcp_listening_socket_list(self, overwrite_list: bool = False):
        # If 'overwrite_list' was set to 'True', we will create new list. The default is 'False', since it is meant to`
        # add new sockets to already existing ones.
        if overwrite_list:
            self.listening_sockets = list()

        # Creating a socket for each port in the list set in configuration file
        for port in self.config['tcp']['listening_port_list']:
            socket_by_port = self.create_socket_ipv4_tcp(
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
                if self.requested_domain_from_dns_server.queue:
                    domain_from_dns_server = self.requested_domain_from_dns_server.queue
                    self.logger.info(f"Requested domain from DNS Server: {self.requested_domain_from_dns_server.queue}")

                # Wait from any connection on "accept()".
                # 'client_socket' is socket or ssl socket, 'client_address' is a tuple (ip_address, port).
                client_socket, client_address, accept_error_message = accepter.accept_connection_with_error(
                    listening_socket_object, dns_domain=domain_from_dns_server, print_kwargs={'logger': self.logger})

                # This is the earliest stage to ask for process name.
                # SSH Remote / LOCALHOST script execution to identify process section.
                # If 'config.tcp['get_process_name']' was set to True in 'config.ini', then this will be executed.
                process_name = None
                if self.config['ssh']['get_process_name']:
                    # Get the process name from the socket.
                    process_name = get_process.get_process_name(
                        client_socket=client_socket, config=self.config, ssh_script_processor=self.ssh_script_processor,
                        print_kwargs={'logger': self.logger})

                # If 'accept()' function worked well, SSL worked well, then 'client_socket' won't be empty.
                if client_socket:
                    # Get the protocol type from the socket.
                    protocol_type, _ = ssl_base.get_protocol_type(client_socket)

                    # If 'protocol_type' was set to 'ssl'.
                    ssl_client_socket = None
                    if protocol_type == 'tls':
                        ssl_client_socket, accept_error_message = \
                            creator.wrap_socket_with_ssl_context_server_sni_extended(
                                client_socket, config=self.config, dns_domain=domain_from_dns_server,
                                print_kwargs={'logger': self.logger})

                        if accept_error_message:
                            # Write statistics after wrap is there was an error.
                            statistics_csv.write_accept_error(
                                error_message=accept_error_message, host=domain_from_dns_server,
                                process_name=process_name,
                                statistics_logger=self.statistics, print_kwargs={'logger': self.logger})

                            continue

                        # ready_to_read, _, _ = select.select([client_socket], [], [])
                        # if ready_to_read:
                        #     try:
                        #         # self.socket_object.do_handshake()
                        #         self.socket_object.accept()
                        #     except Exception:
                        #         raise

                    # Create new arguments tuple that will be passed, since client socket and process_name
                    # are gathered from SocketWrapper.
                    if ssl_client_socket:
                        # In order to use the same object, it needs to get nullified first, since the old instance
                        # will not get overwritten. Though it still will show in the memory as SSLSocket, it will not
                        # be handled as such, but as regular raw socket.
                        client_socket = None
                        client_socket = ssl_client_socket
                    thread_args = \
                        (client_socket, process_name, protocol_type, domain_from_dns_server) + reference_args
                    # If 'pass_function_reference_to_thread' was set to 'False', execute the callable passed function
                    # as is.
                    if not pass_function_reference_to_thread:
                        function_reference(thread_args, *args, **kwargs)
                    # If 'pass_function_reference_to_thread' was set to 'True', execute the callable function reference
                    # in a new thread.
                    else:
                        self.send_accepted_socket_to_thread(function_reference, thread_args)
                # Else, if no client_socket was opened during, accept, then print the error.
                else:
                    # Write statistics after accept.
                    statistics_csv.write_accept_error(
                        error_message=accept_error_message, host=domain_from_dns_server, process_name=process_name,
                        statistics_logger=self.statistics, print_kwargs={'logger': self.logger})
            except Exception:
                print_api("Undocumented exception in while loop of listening sockets.", error_type=True,
                          logger_method="error", traceback_string=True, oneline=True, logger=self.logger)
                pass
                continue

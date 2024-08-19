import socket
import ssl
import time
from typing import Literal, Union

from cryptography import x509

from . import creator
from .receiver import Receiver
from .sender import Sender
from . import ssl_base
from .. import cryptographyw
from ..loggingw import loggingw
from ...print_api import print_api
from ...file_io import file_io

import dns.resolver


class SocketClient:
    logger = loggingw.get_logger_with_level("network." + __name__.rpartition('.')[2])

    def __init__(
            self,
            service_name: str, service_port: int, tls: bool = False, connection_ip=None, dns_servers_list=None):
        """
        If you have a certificate for domain, but not for the IPv4 address, the SSL Socket context can be created for
        domain and the connection itself (socket.connect()) made for the IP. This way YOU decide to which IPv4 your
        domain will connect.

        :param service_name: Should be domain, but can be IPv4 address. In this case SSL Socket will be created to
            IPv4 address.
        :param service_port: Destination server port. Example: 443.
        :param tls: If True, the socket will be created with 'ssl' library wrapper.
        :param connection_ip: (Optional) If specified, the SSL Socket will be created to 'service_name' and
            'socket.connect' will be to specified IPv4 address. If not specified, will be populated from 'socket'
            resolving and available sources. If 'dns_servers_list' specified, will be populated from resolving of the
            'service_name' by these DNS servers, with the first IPv4 result.
        :param dns_servers_list: (Optional) List object with dns IPv4 addresses that 'service_name' will be resolved
            with, using 'dnspython' module. 'connection_ip' will be populated with first resolved IP.

        If both 'connection_ip' and 'dns_servers_list' specified, ValueException with raise.
        """
        self.service_name: str = service_name
        self.service_port: int = service_port
        self.tls: bool = tls
        self.connection_ip = connection_ip
        self.dns_servers_list = dns_servers_list

        self.socket_instance = None

        # If 'connection_ip' was specified, but no 'dns_servers_list', then this IP will be used for 'socket.connect()'.
        # In any way if 'dns_servers_list' the 'connection_ip' will be populated from there and in this case
        # it doesn't matter if you specify the 'connection_ip' manually or not.
        if self.connection_ip and not self.dns_servers_list:
            self.logger.info(
                f"Manual IPv4 address specified. Socket will be created to domain [{self.service_name}] and "
                f"connected to IPv4 [{self.connection_ip}]")
        # If both 'connection_ip' and 'dns_servers_list' specified, raise an exception.
        elif self.connection_ip and self.dns_servers_list:
            raise ValueError("Both 'connection_ip' and 'dns_servers_list' were specified.")

    # Function to create SSL socket to destination service
    def create_service_socket(self):
        # If TLS is enabled.
        if not self.tls:
            self.logger.info(f"Creating non-SSL socket to [{self.service_name}:{self.service_port}]")
            return creator.create_socket_ipv4_tcp()
        else:
            self.logger.info(f"Creating SSL socket to [{self.service_name}:{self.service_port}]")
            socket_object = creator.create_socket_ipv4_tcp()
            return creator.wrap_socket_with_ssl_context_client___default_certs___ignore_verification(
                socket_object, self.service_name)

    def service_connection(self):
        """ Function to establish connection to server """
        # Check if socket to service domain exists.
        # If not
        if not self.socket_instance:
            # Create the socket and connect to it
            self.socket_instance = self.create_service_socket()
        # If the socket exists check if it's still connected. socket.fileno() has value of "-1" if socket
        # was disconnected. We can't do this with previous statement like:
        # if not self.socket_instance or self.socket_instance.fileno() == -1:
        # since if "ssl_socket" doesn't exist we'll get an "UnboundError" on checking "fileno" on it.
        elif self.socket_instance.fileno() == -1:
            # Create the socket and connect to it
            self.socket_instance = self.create_service_socket()
        # If the socket exists and still connected.
        else:
            self.logger.info(
                f"Socket already defined to [{self.service_name}:{self.service_port}]. "
                f"Should be connected - Reusing.")
            # Since, restart the function each send_receive iteration, and there's still a connection we need to
            # set it True, or the socket object will be nullified in the next step.
            return True

        # If 'dns_servers_list' was provided, we will resolve the domain to ip through these servers.
        if self.dns_servers_list:
            self.logger.info(f"DNS Service List specified: {self.dns_servers_list}. "
                             f"Resolving the domain [{self.service_name}]")
            try:
                # The class should be called separately for each thread. You can't create it in the main thread and
                # pass it to threads as object.
                # Building DNS Resolver, it will receive DNS servers from configuration file to contact
                resolver = dns.resolver.Resolver()
                # Assigning the dns service address we acquired from configuration file to resolver
                resolver.nameservers = self.dns_servers_list
                # Get the DNS
                function_server_address = resolver.resolve(self.service_name, 'A')
                # Get only the first entry of the list of IPs [0]
                self.connection_ip = function_server_address[0].to_text()
                self.logger.info(f"Resolved to [{self.connection_ip}]")
            except dns.resolver.NXDOMAIN:
                self.logger.error(f"Domain {self.service_name} doesn't exist - Couldn't resolve with "
                                  f"{self.dns_servers_list}.")
                pass
                return None

        # If DNS was resolved correctly or DNS servers weren't specified - we can try connecting.
        # If 'connection_ip' was manually specified or resolved with 'dnspython' - the connection
        # will be made to the IP.
        if self.connection_ip:
            destination = self.connection_ip
        # If not, then the domain name will be used.
        else:
            destination = self.service_name

        self.logger.info(f"Connecting to [{destination}]")
        try:
            # "connect()" to the server using address and port
            self.socket_instance.connect((destination, self.service_port))
        except ConnectionRefusedError:
            message = f"Couldn't connect to: {self.service_name}. The server is unreachable - Connection refused."
            print_api(message, logger=self.logger, logger_method='error', traceback_string=True, oneline=True)
            # Socket close will be handled in the thread_worker_main
            pass
            return None
        except ConnectionAbortedError:
            message = f"Connection was aborted (by the software on host) to {self.service_name}."
            print_api(message, logger=self.logger, logger_method='error', traceback_string=True, oneline=True)
            # Socket close will be handled in the thread_worker_main
            pass
            return None
        except socket.gaierror:
            message = f"Couldn't resolve [{self.service_name}] to IP using default methods. " \
                      f"Domain doesn't exist or there's no IP assigned to it."
            print_api(message, logger=self.logger, logger_method='error', traceback_string=True, oneline=True)
            # Socket close will be handled in the thread_worker_main
            pass
            return None
        except ssl.SSLError:
            message = f"SSLError raised on connection to {self.service_name}."
            print_api(message, logger=self.logger, logger_method='error', traceback_string=True, oneline=True)
            # Socket close will be handled in the thread_worker_main
            pass
            return None
        except TimeoutError:
            message = f"TimeoutError raised on connection to {self.service_name}."
            print_api(message, logger=self.logger, logger_method='error', traceback_string=True, oneline=True)
            # Socket close will be handled in the thread_worker_main
            pass
            return None
        except ValueError as e:
            message = f'{str(e)} | on connect to [{self.service_name}].'
            print_api(message, logger=self.logger, logger_method='error')
            # Socket close will be handled in the thread_worker_main
            pass
            return None

        # If everything was fine, we'll log the connection.
        self.logger.info("Connected...")

        # Return the connected socket.
        return self.socket_instance

    def get_socket(self):
        return self.socket_instance

    def close_socket(self):
        self.socket_instance.close()
        self.socket_instance = None
        self.logger.info(f"Closed socket to service server [{self.service_name}:{self.service_port}]")

    # noinspection PyUnusedLocal
    def send_receive_to_service(self, request_bytes: bytearray):
        # Define variables
        function_service_data = None
        error_string = None

        # If connection to service server wasn't successful
        if not self.service_connection():
            error_string = "Wasn't able to connect to service, closing the destination service socket"
            print_api(error_string, logger=self.logger, logger_method='error')

            # We'll close the socket and nullify the object
            self.close_socket()
        # If the connection to the service was successful
        else:
            # Getting the IP of the server domain that the socket connected to.
            # We don't need DNS resolving to this IP manually, since if socket connected it means that
            # the socket already got the IP from the DNS server that we passed it from or any other DNS source
            # that was at hand (local DNS cache).
            # Since at this point the connection to the server's domain address was successful - the IP is
            # connectable.
            self.connection_ip = self.socket_instance.getpeername()[0]
            self.logger.info(
                f"[{self.service_name}] resolves to ip: [{self.connection_ip}]. Pulled IP from the socket.")

            # Send the data received from the client to the service over socket
            function_data_sent = Sender(self.socket_instance, request_bytes).send()

            # If the socket disconnected on data send
            if not function_data_sent:
                error_string = "Service socket closed on data send"

                # We'll close the socket and nullify the object
                self.close_socket()
            # Else if send was successful
            else:
                function_service_data = Receiver(self.socket_instance).receive()

                # If data received is empty meaning the socket was closed on the other side
                if not function_service_data:
                    error_string = "Service server closed the connection on receive"

                    # We'll close the socket and nullify the object
                    self.close_socket()

        return function_service_data, error_string, self.connection_ip, self.socket_instance

    def send_receive_message_list_with_interval(
            self, requests_bytes_list: list, intervals_list: list, intervals_defaults: int, cycles: int = 1):
        """
        This function will send a list of requests with provided intervals and receive response.
        * If 'intervals_list' is smaller than 'requests_bytes_list', the missing intervals will be filled with
        'interval_defaults'.
        * If 'requests_bytes_list' is smaller than 'intervals_list', the rest of intervals will be cut.
        * If 'intervals_list' is empty, all the intervals will be filled with 'interval_defaults' values.
        * If 'interval_defaults' is empty, then all the missing intervals will be filled with '0'.
        * 'cycles' in number of times the requests available will be sent.
        """
        # Defining variables
        responses_list: list = list()
        errors_list: list = list()

        # If 'intervals_defaults' is empty we'll fill it with '0'
        if not isinstance(intervals_defaults, int):
            self.logger.info("No 'intervals_defaults' were provided, will be using '0' value.")
            intervals_defaults = 0

        # Checking if specified cycles number is more than 0.
        if cycles < 1:
            self.logger.info("'cycles' provided is less than '0'. Setting '1' by default.")
            cycles = 1

        # If requests list is bigger than intervals list, the missing iterations will be filled with
        # 'intervals_defaults'.
        if len(requests_bytes_list) > len(intervals_list):
            self.logger.info(f"There are more requests than intervals, will be using [{intervals_defaults}] "
                             f"second intervals on missing iterations.")
            # Getting the value of how many iterations are missing.
            intervals_missing_length: int = len(requests_bytes_list) - len(intervals_list)
            # Going through the number of missing iterations and adding default intervals to the intervals list.
            for iterable in range(intervals_missing_length):
                intervals_list.append(intervals_defaults)
        # Else If requests list is smaller than intervals list, then intervals list will be cut to match the length
        # of the requests list.
        elif len(requests_bytes_list) < len(intervals_list):
            self.logger.info("There are less requests than intervals, will be cutting spare intervals.")
            # Getting the number by which the intervals list is bigger.
            intervals_missing_length: int = len(intervals_list) - len(requests_bytes_list)
            # Deleting the number of not needed iterations from the end of intervals_list.
            del intervals_list[-intervals_missing_length]

        # Going through all the cycles.
        for i in range(cycles):
            # If there are more cycles than 1
            if cycles > 1:
                self.logger.info(f"Starting cycle: {i+1}")

            # Going through both lists, since now their length is identical.
            for iterable, (request_raw_bytes, interval_before_message) in \
                    enumerate(zip(requests_bytes_list, intervals_list)):
                self.logger.info(f"Processing request: {iterable+1}. Interval in seconds: {interval_before_message}")
                # If the 'interval_before_message' is '0', there's no need to execute sleep.
                if interval_before_message > 0:
                    self.logger.info(f"Waiting {interval_before_message} seconds")
                    time.sleep(interval_before_message)

                # If "service_client" object is not defined, we'll define it.
                # If it's defined, then it means there's still active "ssl_socket" with connection to the service
                # domain.
                # if not service_client:
                #     service_client = SocketClient(self.service_name, self.service_port)
                # We'll use it when calling the object from outside the class.

                # Sending current client message and receiving a response.
                # If there was an error it will be passed to "client_message" object class and if not, "None" will
                # be passed.
                # If there was connection error or socket close, then "ssl_socket" of the "service_client"
                # will be empty.
                response_raw_bytes, error_string, self.connection_ip, service_ssl_socket = \
                    self.send_receive_to_service(request_raw_bytes)

                # Adding the response to responses list. Same for error.
                responses_list.append(response_raw_bytes)
                errors_list.append(error_string)

                self.logger.info(f"Response: {response_raw_bytes}")
                self.logger.info(f"Error: {error_string}")

                # So if the socket was closed and there was an error we can break the loop.
                # This is needed for more complex operations
                # if not service_ssl_socket:
                #     break

        # Close the socket when the loop has finished
        if self.socket_instance:
            self.close_socket()

        return responses_list, errors_list, self.connection_ip

    def get_certificate_from_server(
            self,
            save_as_file: bool = False,
            cert_file_path: str = None,
            cert_output_type: Literal['der', 'cryptography'] = 'der',
            **kwargs
    ) -> Union[x509.Certificate]:
        """
        This function will get the certificate from the server and return it.

        :param save_as_file: If True, the certificate will be saved to file.
        :param cert_file_path: The path to the file where the certificate will be saved.
        :param cert_output_type: The type of the certificate output.
            'der' - DER bytes format.
            'cryptography' - cryptography.x509.Certificate object.
        """

        # If "save_as_file" is True, then "cert_file_path" must be provided, if not, raise an exception.
        if save_as_file and not cert_file_path:
            raise ValueError("If 'save_as_file' is True, then 'cert_file_path' must be provided.")

        # Connect and get the connected socket.
        server_socket_for_certificate = self.service_connection()
        # Get the DER byte certificate from the socket.
        certificate_from_socket_der_bytes = ssl_base.get_certificate_from_socket(server_socket_for_certificate)
        print_api('Fetched certificate from socket.', logger=self.logger, **kwargs)
        # Close the socket.
        self.close_socket()

        # If "save_as_file" was set to True, and "cert_file_path" was provided, then save the certificate to file.
        if save_as_file and cert_file_path:
            # Convert DER certificate from socket to PEM string format.
            certificate_from_socket_pem_string: str = \
                ssl_base.convert_der_x509_bytes_to_pem_string(certificate_from_socket_der_bytes)

            # Write PEM certificate to file.
            file_io.write_file(
                certificate_from_socket_pem_string, file_path=cert_file_path, logger=self.logger)

        if cert_output_type == 'der':
            return certificate_from_socket_der_bytes
        elif cert_output_type == 'cryptography':
            # Convert DER certificate from socket to X509 cryptography module object.
            return cryptographyw.convert_der_to_x509_object(certificate_from_socket_der_bytes)

import sys
import socket
import ssl
import time

from ..logger_custom import CustomLogger
from .receiver import Receiver
from .sender import Sender

# External libraries
try:
    import dns.resolver
except ImportError as exception_object:
    print(f"Library missing: {exception_object.name}. Install by executing: pip install dnspython")
    sys.exit()


class SocketClient:
    logger = CustomLogger("network." + __name__.rpartition('.')[2])

    # noinspection GrazieInspection
    def __init__(self, service_name: str, service_port: int, service_ip=None, dns_servers_list=None):
        """
        If you have a certificate for domain, but not for the IPv4 address, the SSL Socket context can be created for
        domain and the connection itself (socket.connect()) made for the IP. This way YOU decide to which IPv4 your
        domain will connect.

        :param service_name: Should be domain, but can be IPv4 address. In this case SSL Socket will be created to
            IPv4 address.
        :param service_port: Destination server port. Example: 443.
        :param service_ip: (Optional) If specified, the SSL Socket will be created to 'service_name' and '.connect'
            will be to specified IPv4 address. If not specified, will be populated from 'socket' resolving and
            available sources.
        :param dns_servers_list: (Optional) List object with dns IPv4 addresses that 'service_name' will be resolved
            with, using 'dnspython' module. 'service_ip' will be populated with first resolved IP.
        """
        self.service_name: str = service_name
        self.service_port: int = service_port
        self.service_ip = service_ip
        self.dns_servers_list = dns_servers_list

        self.ssl_socket = None

        # If 'service_ip' was specified, but no 'dns_servers_list', then this IP will be used for 'socket.connect()'.
        # In any way if 'dns_servers_list' the 'service_ip' will be populated from there and in this case
        # it doesn't matter if you specify the 'service_ip' manually or not.
        if self.service_ip and not self.dns_servers_list:
            self.logger.info(
                f"Manual IPv4 address specified. SSL Socket will be created to domain [{self.service_name}] and "
                f"connected to IPv4 [{self.service_ip}]")

    # Function to create SSL socket to destination service
    def create_service_ssl_socket(self):
        self.logger.info(f"Creating SSL socket to [{self.service_name}:{self.service_port}]")

        # When using with statement, no need to use "socket.close()" method to disconnect when finished
        # AF_INET - Socket family of IPv4
        # SOCK_STREAM - Socket type of TCP
        socket_object: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Create ssl context object
        ssl_context: ssl.SSLContext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        # Specifying the minimum TLS version to work with
        # function_context.minimum_version = ssl.TLSVersion.TLSv1_2
        # Specifying the maximum TLS version to work with
        # function_context.maximum_version = ssl.TLSVersion.TLSv1_2
        # "load_default_certs" method is telling the client to check the local certificate storage on the system for the
        # needed certificate of the server. Without this line you will get an error from the server that the client
        # is using self-signed certificate. Which is partly true, since you used the SLL wrapper,
        # but didn't specify the certificate at all.
        # The purpose of the certificate is to authenticate on the server
        # context.load_default_certs(Purpose.SERVER_AUTH)
        # You don't have to specify the purpose to connect, but if you get a purpose error, you know where to find it
        ssl_context.load_default_certs()

        # If we want to ignore bad server certificates when connecting as a client, we need to think about security.
        # If you care, you should not need to do it, for MITM possibilities.
        # To do this anyway we need first to disable 'check_hostname' and only
        # then set 'verify_mode' to 'ssl.CERT_NONE'. If we do it in backwards order, when 'verify_mode' comes before
        # 'check_hostname' then we'll get an exception that 'check_hostname' needs to be False.
        # This setting should eliminate ssl error on 'SSLSocket.connect()':
        # ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED]
        # certificate verify failed: unable to get local issuer certificate (_ssl.c:997)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        # Wrapping the socket with "ssl.SSLContext" object to make "ssl.SSLSocket" object.
        # With "server_hostname" you don't have to use DNS hostname, you can use the IP, just remember to add
        # the address to your Certificate under "X509v3 Subject Alternative Name"
        # SSL wrapping should happen after socket creation and before connection:
        # https://docs.python.org/3/library/ssl.html
        self.ssl_socket: ssl.SSLSocket = ssl_context.wrap_socket(sock=socket_object,
                                                                 server_side=False,
                                                                 server_hostname=self.service_name)

        return self.ssl_socket

    # noinspection PyBroadException
    def service_connection_with_error_handling(self):
        """ Function to establish connection to server """
        # Defining result boolean variable, which would mean that connection succeeded
        function_result: bool = True

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
                self.service_ip = function_server_address[0].to_text()
                self.logger.info(f"Resolved to [{self.service_ip}]")
            except dns.resolver.NXDOMAIN:
                self.logger.error(f"Domain {self.service_name} doesn't exist - Couldn't resolve with "
                                  f"{self.dns_servers_list}.")
                pass
                function_result = False

        # If DNS was resolved correctly or DNS servers weren't specified, this will be True, and we can try connecting.
        if function_result:
            # If 'service_ip' was manually specified or resolved with 'dnspython' - the connection
            # will be made to the IP.
            if self.service_ip:
                destination = self.service_ip
            # If not, then the domain name will be used.
            else:
                destination = self.service_name

            self.logger.info(f"Connecting to [{destination}]")
            try:
                # "connect()" to the server using address and port
                self.ssl_socket.connect((destination, self.service_port))
            except ConnectionRefusedError:
                self.logger.error_exception_oneliner(
                    f"Couldn't connect to: {self.service_name}. The server is unreachable - Connection refused.")
                # Socket close will be handled in the thread_worker_main
                function_result = False
                pass
            except ConnectionAbortedError:
                self.logger.error_exception_oneliner(
                    f"Connection was aborted (by the software on host) to {self.service_name}.")
                # Socket close will be handled in the thread_worker_main
                function_result = False
                pass
            except socket.gaierror:
                self.logger.error_exception_oneliner(f"Couldn't resolve [{self.service_name}] to IP using default "
                                                     f"methods. Domain doesn't exist or there's no IP assigned to it.")
                # Socket close will be handled in the thread_worker_main
                function_result = False
                pass
            except ssl.SSLError:
                self.logger.error_exception_oneliner(f"SSLError raised on connection to {self.service_name}.")
                # Socket close will be handled in the thread_worker_main
                function_result = False
                pass
            except TimeoutError:
                self.logger.error_exception_oneliner(f"TimeoutError raised on connection to {self.service_name}.")
                # Socket close will be handled in the thread_worker_main
                function_result = False
                pass
            except Exception:
                self.logger.error_exception_oneliner(f"Unknown exception raised, while connection to "
                                                     f"{self.service_name}.")
                # Socket close will be handled in the thread_worker_main
                function_result = False
                pass

            if function_result:
                # print(f"Connected to server {function_server_address_from_socket} on
                # {function_server_port_from_socket}")
                self.logger.info("Connected...")

        return function_result

    def close_socket(self):
        self.ssl_socket.close()
        self.ssl_socket = None
        self.logger.info(f"Closed socket to service server [{self.service_name}:{self.service_port}]")

    # noinspection PyUnusedLocal
    def send_receive_to_service(self, request_bytes: bytearray):
        # Define variables
        function_service_data = None
        error_string = None
        # At this stage the service domain wasn't connected, so we'll set it False
        function_service_connection: bool = False

        # Check if socket to service domain exists.
        # If not
        if not self.ssl_socket:
            # Create the socket and connect to it
            self.ssl_socket = self.create_service_ssl_socket()
            function_service_connection = self.service_connection_with_error_handling()
        # If the socket exists check if it's still connected. socket.fileno() has value of "-1" if socket
        # was disconnected. We can't do this with previous statement like:
        # if not self.ssl_socket or self.ssl_socket.fileno() == -1:
        # since if "ssl_socket" doesn't exist we'll get an "UnboundError" on checking "fileno" on it.
        elif self.ssl_socket.fileno() == -1:
            # Create the socket and connect to it
            self.ssl_socket = self.create_service_ssl_socket()
            function_service_connection = self.service_connection_with_error_handling()
        # If the socket exists and still connected.
        else:
            self.logger.info(
                f"SSL Socket already defined to [{self.service_name}:{self.service_port}]. "
                f"Should be connected - Reusing.")
            # Since, restart the function each send_receive iteration, and there's still a connection we need to
            # set it True, or the socket object will be nullified in the next step.
            function_service_connection = True

        # If connection to service server wasn't successful
        if not function_service_connection:
            error_string = "Wasn't able to connect to service, closing the destination service socket"
            self.logger.error_exception_oneliner(error_string)

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
            self.service_ip = self.ssl_socket.getpeername()[0]
            self.logger.info(f"[{self.service_name}] resolves to ip: [{self.service_ip}]. Pulled IP from the socket.")

            # Send the data received from the client to the service over socket
            function_data_sent = Sender(self.ssl_socket, request_bytes).send()

            # If the socket disconnected on data send
            if not function_data_sent:
                error_string = "Service socket closed on data send"

                # We'll close the socket and nullify the object
                self.close_socket()
            # Else if send was successful
            else:
                function_service_data = Receiver(self.ssl_socket).receive()

                # If data received is empty meaning the socket was closed on the other side
                if not function_service_data:
                    error_string = "Service server closed the connection on receive"

                    # We'll close the socket and nullify the object
                    self.close_socket()

        return function_service_data, error_string, self.service_ip, self.ssl_socket

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
                response_raw_bytes, error_string, self.service_ip, service_ssl_socket = \
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
        if self.ssl_socket:
            self.close_socket()

        return responses_list, errors_list, self.service_ip

import os
import datetime
import time
import threading
import socket
import logging
from pathlib import Path
from typing import Literal

from ...print_api import print_api
from ..loggingw import loggingw
from ..psutilw import networks
from ... import queues
from ...basics import booleans, tracebacks
from ...file_io import csvs

# noinspection PyPackageRequirements
import dnslib
# noinspection PyPackageRequirements
from dnslib import DNSRecord, DNSHeader, RR, A


class DnsPortInUseError(Exception):
    pass


class DnsConfigurationValuesError(Exception):
    pass


LOGGER_NAME: str = 'dns_traffic'
DNS_STATISTICS_HEADER: str = (
    'timestamp,dns_type,client_ipv4,client_port,qname,qtype,qclass,header,error')


class DnsStatisticsCSVWriter:
    """
    Class to write statistics to CSV file.
    This can be initiated at the main, and then passed to the thread worker function.
    """
    def __init__(
            self,
            statistics_directory_path: str
    ):
        self.csv_logger = loggingw.create_logger(
            logger_name=LOGGER_NAME,
            directory_path=statistics_directory_path,
            add_timedfile=True,
            formatter_filehandler='MESSAGE',
            file_type='csv',
            header=DNS_STATISTICS_HEADER
        )

    def write_row(
            self,
            client_address: tuple,
            timestamp=None,
            dns_type: Literal['request', 'response'] = None,
            dns_request = None,
            dns_response = None,
            error: str = None,
    ):
        if not timestamp:
            timestamp = datetime.datetime.now()

        if not dns_type:
            if not dns_request and not dns_response:
                raise ValueError("Either DNS Request or DNS Response must be provided.")
            elif dns_request and dns_response:
                raise ValueError("Either DNS Request or DNS Response must be provided. Not both.")

        if dns_request:
            dns_type = 'request'
        elif dns_response:
            dns_type = 'response'

        if dns_type not in ['request', 'response']:
            raise ValueError(f"DNS Type can be only 'request' or 'response'. Provided: {dns_type}")

        client_ipv4, client_port = client_address
        client_ipv4: str
        client_port: str = str(client_port)

        qname: str = str()
        qtype: str = str()
        qclass: str = str()
        rr: str = str()
        header: str = str()

        if dns_request:
            qname = str(dns_request.q.qname)[:-1]
            qtype = dnslib.QTYPE[dns_request.q.qtype]
            qclass = dnslib.CLASS[dns_request.q.qclass]

        if dns_response:
            qname = str(dns_response.q.qname)[:-1]
            qtype = dnslib.QTYPE[dns_response.q.qtype]
            qclass = dnslib.CLASS[dns_response.q.qclass]
            rr: str = str(dns_response.rr)
            header = str(dns_response.header)

        escaped_line_string: str = csvs.escape_csv_line_to_string([
            timestamp,
            dns_type,
            client_ipv4,
            client_port,
            qname,
            qtype,
            qclass,
            rr,
            header,
            error
        ])

        self.csv_logger.info(escaped_line_string)

    def write_error(
            self,
            dns_type: Literal['request', 'response'],
            error_message: str,
            client_address: tuple
    ):
        """
        Write the error message to the statistics CSV file.
        This is used for easier execution, since most of the parameters will be empty on accept.

        :param dns_type: Literal['request', 'response'], DNS request or response.
        :param error_message: string, error message.
        :param client_address: tuple, client address (IPv4, Port).
        :return:
        """

        self.write_row(
            dns_type=dns_type,
            client_address=client_address,
            error=error_message
        )


class DnsServer:
    """
    DnsServer class is responsible to handle DNS Requests on port 53 based on configuration and send DNS Response back.
    """
    # noinspection PyPep8Naming
    def __init__(
            self,
            listening_interface: str,
            listening_port: int,
            log_directory_path: str,
            backupCount_log_files_x_days: int = 0,
            forwarding_dns_service_ipv4: str = '8.8.8.8',
            forwarding_dns_service_port: int = 53,
            resolve_to_tcp_server_only_tcp_resolve_domains: bool = False,
            resolve_to_tcp_server_all_domains: bool = False,
            resolve_regular: bool = False,
            offline_mode: bool = False,
            tcp_target_server_ipv4: str = '127.0.0.1',
            tcp_resolve_domain_list: list = None,
            request_domain_queue: queues.NonBlockQueue = None,
            buffer_size_receive: int = 8192,
            response_ttl: int = 60,
            dns_service_retries: int = 5,
            cache_timeout_minutes: int = 60,
            logger: logging.Logger = None
    ):
        """
        Initialize the DNS Server object with all the necessary settings.

        :param listening_interface: str: Interface that the DNS Server will listen on.
            Example: '0.0.0.0'. For all interfaces.
        :param listening_port: int: Port number that the DNS Server will listen on.
        :param log_directory_path: str: Path to the directory where the logs will be saved.
        :param backupCount_log_files_x_days: int: How many days the log files will be kept.
            Default is 0, which means that the log files will be kept indefinitely.
            More than 0 means that the log files will be deleted after the specified days.
        :param forwarding_dns_service_ipv4: str: IPv4 address of the DNS Service that will be used for resolving.
            Example: '8.8.8.8'. For Google DNS Service.
        :param forwarding_dns_service_port: int: Port number of the DNS Service that will be used for resolving.
            Default is 53.
        :param resolve_to_tcp_server_only_tcp_resolve_domains: bool: If the DNS Server should route only the
            domains from 'tcp_resolve_domain_list' to the TCP Server in 'tcp_target_server_ipv4'.
        :param resolve_to_tcp_server_all_domains: bool: If the DNS Server should route all domains to the TCP Server.
        :param resolve_regular: bool: If the DNS Server should resolve all the domains to the Live DNS Service.
        :param offline_mode: bool: If the DNS Server should work in offline mode.
        :param tcp_target_server_ipv4: str: IPv4 address of the TCP Server that the specified booleans will resolve
            the domains to.
        :param tcp_resolve_domain_list: list: List of domains that will be resolved to the TCP Server.
            This means that all the requests will be resolved to the specified offline IPv4 address.
        :param request_domain_queue: queues.NonBlockQueue: Queue to pass all the requested domains that hit the DNS
        :param buffer_size_receive: int: Buffer size of the connection while receiving messages.
        :param response_ttl: int, Time to live of the DNS Response that will be returned. Default is 60 seconds.
        :param dns_service_retries: int, How many times the request will be sent to forwarded DNS Service on errors:
            (socket connect / request send / response receive).
        :param cache_timeout_minutes: int: Timeout in minutes to clear the DNS Cache.
            server. Each domain will be pass in the queue as a string.
        :param logger: logging.Logger: Logger object to use for logging. If not provided, a new logger will be created.
        """

        self.listening_interface: str = listening_interface
        self.listening_port: int = listening_port
        self.log_directory_path: str = log_directory_path
        self.forwarding_dns_service_ipv4: str = forwarding_dns_service_ipv4
        self.forwarding_dns_service_port: int = forwarding_dns_service_port
        self.tcp_target_server_ipv4: str = tcp_target_server_ipv4
        self.tcp_resolve_domain_list: list = tcp_resolve_domain_list
        self.offline_mode: bool = offline_mode
        self.resolve_to_tcp_server_only_tcp_resolve_domains: bool = resolve_to_tcp_server_only_tcp_resolve_domains
        self.resolve_to_tcp_server_all_domains: bool = resolve_to_tcp_server_all_domains
        self.resolve_regular: bool = resolve_regular
        self.request_domain_queue: queues.NonBlockQueue = request_domain_queue
        self.buffer_size_receive: int = buffer_size_receive
        self.response_ttl: int = response_ttl
        self.dns_service_retries: int = dns_service_retries
        self.cache_timeout_minutes: int = cache_timeout_minutes

        if not tcp_resolve_domain_list:
            self.tcp_resolve_domain_list = list()
        else:
            self.tcp_resolve_domain_list = tcp_resolve_domain_list

        # Settings for static DNS Responses in offline mode.
        self.offline_route_ipv4: str = '10.10.10.10'
        self.offline_route_ipv6: str = 'fe80::3c09:df29:d52b:af39'
        self.offline_route_domain: str = 'domain.com'
        self.offline_srv_answer: str = \
            '.                       86391   IN      SOA     domain.com. domain.com. 2022012500 1800 900 604800 86400'
        # self.offline_https_answer: str = str()

        # If forwarding to Live DNS Service fails. Currently, we didn't send anything, so it's 'False'.
        self.retried: bool = False
        # Defining cache dictionary for assigning DNS Questions to DNS Answers
        self.dns_questions_to_answers_cache: dict = dict()

        # Filename to save all the known domains and their relative IPv4 addresses.
        self.known_domains_filename: str = 'dns_known_domains.txt'
        # Filename to save all the known IPv4 addresses and their relative domains.
        self.known_ipv4_filename: str = 'dns_known_ipv4.txt'
        # Filename to save domains and their IPv4 addresses by time they hit the DNS server.
        self.known_dns_ipv4_by_time_filename: str = 'dns_ipv4_by_time.txt'

        # Logger that logs all the DNS Requests and responses in DNS format. These entries will not present in
        # network log of TCP Server module.
        self.dns_statistics_csv_writer = DnsStatisticsCSVWriter(statistics_directory_path=log_directory_path)

        # Check if the logger was provided, if not, create a new logger.
        if not logger:
            self.logger = loggingw.create_logger(
                logger_name=Path(__file__).stem,
                directory_path=self.log_directory_path,
                add_stream=True,
                add_timedfile=True,
                formatter_streamhandler='DEFAULT',
                formatter_filehandler='DEFAULT',
                backupCount=backupCount_log_files_x_days
            )
        else:
            # Create child logger for the provided logger with the module's name.
            self.logger: logging.Logger = loggingw.get_logger_with_level(f'{logger.name}.{Path(__file__).stem}')

        self.test_config()

    def test_config(self):
        try:
            booleans.is_only_1_true_in_list(
                booleans_list_of_tuples=[
                    (self.resolve_to_tcp_server_only_tcp_resolve_domains,
                     'resolve_to_tcp_server_only_tcp_resolve_domains'),
                    (self.resolve_to_tcp_server_all_domains, 'resolve_to_tcp_server_all_domains'),
                    (self.resolve_regular, 'resolve_regular')
                ],
                raise_if_all_false=True
            )
        except ValueError as e:
            raise DnsConfigurationValuesError(e)

        port_in_use = networks.get_processes_using_port_list([self.listening_port])
        if port_in_use:
            error_messages: list = list()
            for port, process_info in port_in_use.items():
                error_messages.append(f"Port [{port}] is already in use by process: {process_info}")
            raise DnsPortInUseError("\n".join(error_messages))

    def thread_worker_empty_dns_cache(self, function_sleep_time: int):
        """
        A thread worker function to empty the cache of DNS request and response lists.

        :return: None.
        """

        while True:
            time.sleep(function_sleep_time * 60)
            self.dns_questions_to_answers_cache = dict()
            self.logger.info("*** DNS cache cleared")

    def start(self):
        """
        Main DNS Server function to start it.

        :return: None.
        """

        self.logger.info("DNS Server Module Started.")

        # Define objects for global usage
        forward_to_tcp_server: bool = bool()
        # IPv4 address list, to export to different text log files.
        ipv4_addresses: list = list()
        # Aggregation of all the A records domains and their IPv4 answers.
        known_a_records_domains_dict: dict = dict()
        # Aggregation of all the A records IPv4 addresses and their domains.
        known_a_records_ipv4_dict: dict = dict()

        # Check if 'route_to_tcp_server_only_engine_domains' was set to 'True' and output message accordingly.
        if self.resolve_to_tcp_server_only_tcp_resolve_domains:
            message = "Routing only engine domains to Built-in TCP Server."
            print_api(message, logger=self.logger)

            message = f"Current engine domains: {self.tcp_resolve_domain_list}"
            print_api(message, logger=self.logger, color='green')

        if self.resolve_to_tcp_server_all_domains:
            message = "Routing all domains to Built-in TCP Server."
            print_api(message, logger=self.logger, color='blue')

        if self.resolve_regular:
            message = f"Routing all domains to Live DNS Service: {self.forwarding_dns_service_ipv4}"
            print_api(message, logger=self.logger, color='green')

        # The list that will hold all the threads that can be joined later
        threads_list: list = list()

        # Starting a thread that will empty the DNS Cache lists
        thread_current = threading.Thread(target=self.thread_worker_empty_dns_cache,
                                          args=(self.cache_timeout_minutes,))
        thread_current.daemon = True
        # Start the thread
        thread_current.start()
        # Append to list of threads, so they can be "joined" later
        threads_list.append(thread_current)

        # To handle DNS requests UDP socket is needed.
        # AF_INET - Socket family of IPv4
        # SOCK_DGRAM - Socket type of UDP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as main_socket_object:
            main_socket_object: socket.socket

            # Binding / assigning the port to the server / this script, that is going to be used for
            # receiving connections.
            main_socket_object.bind((self.listening_interface, self.listening_port))

            while True:
                # Needed this logging line when DNS was separate process.
                # self.logger.info("Waiting to receive new requests...")

                # noinspection PyBroadException
                try:
                    client_data, client_address = main_socket_object.recvfrom(self.buffer_size_receive)
                    client_data: bytes
                    client_address: tuple
                except ConnectionResetError:
                    traceback_string = tracebacks.get_as_string(one_line=True)
                    # This error happens when the client closes the connection before the server.
                    # This is not an error for a DNS Server, but we'll log it anyway only with the full DNS logger.
                    message = (f"Error: to receive DNS request, An existing connection was forcibly closed | "
                               f"{traceback_string}")
                    self.dns_statistics_csv_writer.write_error(
                        dns_type='request', client_address=client_address, error_message=message)
                    pass
                    continue
                except Exception:
                    message = "Unknown Exception: to receive DNS request"
                    print_api(
                        message, logger=self.logger, logger_method='critical', traceback_string=True)
                    pass
                    continue

                # noinspection PyBroadException
                try:
                    # This is the real point when the request received was logged, but since it takes too much place
                    # on the screen, moved it to full request logging position.
                    # message = f"Received request from: {client_address}"
                    # self.logger.info(message)
                    # self.dns_full_logger.info(message)

                    # Received DNS request that needs to be parsed to readable format
                    dns_object: dnslib.dns.DNSRecord = DNSRecord.parse(client_data)
                    # "qtype" returns as numeric identification, we need to convert it to
                    # Readable QType (DNS Record Type) provided by the dnslib
                    # "dns_object.q" is the Question from the client that holds all the DNS question data,
                    # like which domain was questioned for resolving,
                    # the class (example: IN), DNS Record Type that was questioned and a header.
                    # "dns_object.q.qtype" returns only QType of the Question
                    qtype_string: str = dnslib.QTYPE[dns_object.q.qtype]
                    # "qclass" returns as numeric identification, we need to convert it
                    # to Readable QCLASS (DNS Record CLASS) provided by the dnslib.
                    # "dns_object.q.qclass" returns only QCLASS of the Question
                    qclass_string: str = dnslib.CLASS[dns_object.q.qclass]
                    # To check all the available QCLASSes or QTYPEs:
                    # vars(dnslib.CLASS)
                    # vars(dnslib.QTYPE)
                    # To check more methods of 'dnslib':
                    # dir(dnslib)

                    # "dns_object.q.qname" returns only the questioned domain with "." (dot) in the end,
                    # which needs to be removed.
                    question_domain: str = str(dns_object.q.qname)[:-1]
                    self.dns_statistics_csv_writer.write_row(client_address=client_address, dns_request=dns_object)

                    message = (f"Received DNS request: {question_domain} | {qclass_string} | {qtype_string} |   "
                               f"From: {client_address}.")
                    self.logger.info(message)

                    # Nullifying the DNS cache for current request before check.
                    dns_cached_request = False
                    # Check if the received data request from client is already in the cache
                    if client_data in self.dns_questions_to_answers_cache:
                        # message = "!!! Question / Answer is already in the dictionary..."
                        # self.logger.info(message)

                        # Get the response from the cached answers list
                        dns_response = self.dns_questions_to_answers_cache[client_data]

                        # Since the request is already in the cached dictionary, we'll set the flag for later usage.
                        dns_cached_request = True
                    # If current request is not in the cache.
                    else:
                        # Check if the incoming Record is "A" record.
                        if qtype_string == "A":
                            # Check if 'resolve_to_tcp_server_only_tcp_resolve_domains' is set to 'True'.
                            # If so, we need to check if the incoming domain contain any of the domains in the list.
                            if self.resolve_to_tcp_server_only_tcp_resolve_domains:
                                # If current query domain (+ subdomains) CONTAIN any of the domains from modules config
                                # files and current request contains "A" (IPv4) record.
                                if any(x in question_domain for x in self.tcp_resolve_domain_list):
                                    # If incoming domain contains any of the 'engine_domains' then domain will
                                    # be forwarded to our TCP Server.
                                    forward_to_tcp_server = True
                                else:
                                    forward_to_tcp_server = False

                            # If 'route_to_tcp_server_all_domains' was set to 'False' in 'config.ini' file then
                            # we'll forward all 'A' records domains to the Built-in TCP Server.
                            if self.resolve_to_tcp_server_all_domains:
                                forward_to_tcp_server = True

                            # If 'regular_resolving' was set to 'True' in 'config.ini' file then
                            # we'll forward all 'A' records domains to the Live DNS Service.
                            if self.resolve_regular:
                                forward_to_tcp_server = False

                        # If incoming record is not an "A" record, then it will not be forwarded to our TCP Server.
                        else:
                            forward_to_tcp_server = False

                        # If 'forward_to_tcp_server' is 'True' we'll resolve the record with our TCP Server IP address.
                        if forward_to_tcp_server:
                            # If the request is forwarded to TCP server, then we'll put the domain in the domain queue.
                            # self.request_domain_queue.put(question_domain)
                            self.request_domain_queue.queue = question_domain

                            # Make DNS response that will refer TCP traffic to our server
                            dns_built_response = DNSRecord(
                                # dns_object.header,
                                DNSHeader(id=dns_object.header.id, qr=1, aa=1, ra=1),
                                # q=DNSQuestion(question_domain),
                                q=dns_object.q,
                                a=RR(question_domain,
                                     rdata=A(self.tcp_target_server_ipv4),
                                     ttl=self.response_ttl)
                            )
                            # Encode the response that was built above to legit DNS Response
                            dns_response = dns_built_response.pack()

                        # The rest of the records that doesn't contain relevant domains from modules configuration
                        # If current query domain (+ subdomains) DOESN'T CONTAIN
                        # any of the domains from modules config files
                        else:
                            # If we're in offline mode
                            if self.offline_mode:
                                # Make DNS response that will refer TCP traffic to our server
                                # dns_question = DNSRecord.question(question_domain)
                                dns_built_response = dns_object.reply()

                                # Trying to create response.
                                # noinspection PyBroadException
                                try:
                                    if qtype_string == "AAAA":
                                        dns_built_response.add_answer(
                                            *RR.fromZone(
                                                f'{question_domain} {str(self.response_ttl)} {qtype_string} '
                                                f'{self.offline_route_ipv6}')
                                        )

                                        message = f"!!! Question / Answer is in offline mode returning " \
                                                  f"{self.offline_route_ipv6}."
                                        self.logger.info(message)

                                    # SRV Record type explanation:
                                    # https://www.cloudflare.com/learning/dns/dns-records/dns-srv-record/
                                    # Query example:
                                    # _xmpp._tcp.example.com. 86400 IN SRV 10 5 5223 server.example.com.
                                    # Answer example:
                                    # .                       86391   IN      SRV     domain.
                                    # com. domain.com. 2022012500 1800 900 604800 86400
                                    # Basically SOA is the same, but can be with additional fields.
                                    # Since, it's offline and not online - we don't really care.
                                    elif qtype_string == "SRV" or qtype_string == "SOA" or qtype_string == "HTTPS":
                                        dns_built_response.add_answer(*RR.fromZone(self.offline_srv_answer))

                                        message = f"!!! Question / Answer is in offline mode returning: " \
                                                  f"{self.offline_srv_answer}."
                                        self.logger.info(message)
                                    elif qtype_string == "ANY":
                                        dns_built_response.add_answer(
                                            *RR.fromZone(question_domain + " " + str(self.response_ttl) + " CNAME " +
                                                         self.offline_route_domain)
                                        )

                                        message = f"!!! Question / Answer is in offline mode returning " \
                                                  f"{self.offline_route_domain}."
                                        self.logger.info(message)
                                    else:
                                        dns_built_response.add_answer(
                                            *RR.fromZone(
                                                question_domain + " " + str(self.response_ttl) + " " + qtype_string +
                                                " " + self.offline_route_ipv4)
                                        )

                                        message = f"!!! Question / Answer is in offline mode returning " \
                                                  f"{self.offline_route_ipv4}."
                                        self.logger.info(message)
                                # Values error means in most cases that you create wrong response
                                # for specific type of request.
                                except ValueError:
                                    message = f"Looks like wrong type of response for QTYPE: {qtype_string}. Response: "
                                    print_api(message, logger=self.logger, logger_method='critical',
                                              traceback_string=True)
                                    print_api(f"{dns_built_response}", logger=self.logger, logger_method='critical',
                                              traceback_string=True)
                                    # Pass the exception.
                                    pass
                                    # Continue to the next DNS request, since there's nothing to do here right now.
                                    continue
                                # General exception in response creation.
                                except Exception:
                                    message = \
                                        (f"Unknown exception while creating response for QTYPE: {qtype_string}. "
                                         f"Response: \n{dns_built_response}")
                                    print_api(message, logger=self.logger, logger_method='critical',
                                              traceback_string=True)
                                    # Pass the exception.
                                    pass
                                    # Continue to the next DNS request, since there's nothing to do here right now.
                                    continue

                                # Encode the response that was built above to legit DNS Response
                                dns_response = dns_built_response.pack()
                            # If we're in online mode
                            else:
                                counter = 0
                                retried = False
                                # If counter isn't equal to number of retries that were set in
                                # 'dns_service_retries' - we'll loop.
                                while counter != self.dns_service_retries + 1:
                                    # If counter is bigger than 0 it means that we're retrying.
                                    # No need to print it if it's 0.
                                    # Since, it's probably going to succeed.
                                    if counter > 0:
                                        self.logger.info(f"Retry #: {counter}/{self.dns_service_retries}")
                                    self.logger.info(
                                        f"Forwarding request. Creating UDP socket to: "
                                        f"{self.forwarding_dns_service_ipv4}:"
                                        f"{self.forwarding_dns_service_port}")
                                    try:
                                        google_dns_ipv4_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                                        google_dns_ipv4_socket.settimeout(5)

                                        message = "Socket created, Forwarding..."
                                        # self.logger.info(message)
                                        self.logger.info(message)

                                        google_dns_ipv4_socket.sendto(client_data, (
                                            self.forwarding_dns_service_ipv4,
                                            self.forwarding_dns_service_port
                                        ))
                                        # The script needs to wait a second or receive can hang
                                        message = "Request sent to the forwarding DNS, Receiving the answer..."
                                        # self.logger.info(message)
                                        self.logger.info(message)

                                        dns_response, google_address = \
                                            google_dns_ipv4_socket.recvfrom(self.buffer_size_receive)
                                    except TimeoutError as function_exception_object:
                                        print_api(function_exception_object, logger=self.logger, logger_method='error',
                                                  traceback_string=True, oneline=True)
                                        google_dns_ipv4_socket.close()
                                        counter += 1
                                        # Pass the exception.
                                        pass

                                        # If counter reached the maximum retries set, we'll wait for amount of time
                                        # that was set to wait before continuing to the next retry cycle.
                                        if counter == self.dns_service_retries + 1:
                                            retried = True
                                            self.logger.info(
                                                f"Retried {self.dns_service_retries} times. "
                                                f"Couldn't forward DNS request to: "
                                                f"[{self.forwarding_dns_service_ipv4}]. "
                                                f"Continuing to next request.")

                                        # From here continue to the next iteration of While loop.
                                        continue

                                    # At this point the connection was successful, we can break the loop.
                                    break

                                # If retried connecting to Live DNS Service and failed,
                                # then continue to next iteration (request).
                                if retried:
                                    continue

                                self.logger.info(
                                    f"Answer received from: {self.forwarding_dns_service_ipv4}")

                                # Closing the socket to forwarding service
                                google_dns_ipv4_socket.close()
                                self.logger.info("Closed socket to forwarding service")

                                # Appending current DNS Request and DNS Answer to the Cache
                                self.dns_questions_to_answers_cache.update({client_data: dns_response})

                    # If 'forward_to_tcp_server' it means that we built the response, and we don't need to reparse it,
                    # since we already have all the data.
                    if forward_to_tcp_server:
                        # self.logger.info(f"Response {dns_built_response.short()}")
                        self.dns_statistics_csv_writer.write_row(
                            client_address=client_address, dns_response=dns_built_response)

                        message = f"Response Details: {dns_built_response.rr}"
                        print_api(message, logger=self.logger, logger_method='info', oneline=True)

                        # message = f"Response Full Details: {dns_built_response.format(prefix='', sort=True)}"
                        # print_api(message, logger=self.logger, logger_method='info', oneline=True)

                        # Now we can turn it to false, so it won't trigger this
                        # condition next time if the response was not built
                        # by the server.
                        forward_to_tcp_server = False
                    # This means that the response wasn't built at this iteration.
                    # Could be fetched from cache dictionary or from
                    # Live DNS Service.
                    else:
                        # Parsing the response to output to console
                        dns_response_parsed: dnslib.dns.DNSRecord = DNSRecord.parse(dns_response)

                        # Reinitializing the ipv4 addresses list.
                        ipv4_addresses = list()

                        # If the DNS answer section isn't empty, and log the returned IPv4 addresses.
                        if dns_response_parsed.rr:
                            for rr in dns_response_parsed.rr:
                                if isinstance(rr.rdata, A):
                                    self.dns_statistics_csv_writer.write_row(
                                        client_address=client_address, dns_response=dns_response_parsed)

                                    self.logger.info(f"Response IP: {rr.rdata}")

                                    # Adding the address to the list as 'str' object and not 'dnslib.dns.A'.
                                    ipv4_addresses.append(str(rr.rdata))

                        # message = f"Response Details: {dns_response_parsed.rr}"
                        # print_api(message, logger=self.dns_statistics_csv_writer, logger_method='info', oneline=True)
                        #
                        # message = f"Response Full Details: {dns_response_parsed}"
                        # print_api(message, logger=self.dns_statistics_csv_writer, logger_method='info', oneline=True)

                    self.logger.info("Sending DNS response back to client...")
                    main_socket_object.sendto(dns_response, client_address)
                    self.logger.info("DNS Response sent...")

                    # 'ipv4_addresses' list contains entries of type 'dnslib.dns.A' and not string.
                    # We'll convert each entry to string, so strings can be searched in this list.
                    # for index, ip_address in enumerate(ipv4_addresses):
                    #     ipv4_addresses[index] = str(ip_address)

                    # ==================================================================================================
                    # # Known domain dictionary of last 2 A records' management.
                    #
                    # # Sorting the addresses, so it will be easier to compare dictionaries in the list.
                    # ipv4_addresses_sorted = sorted(ipv4_addresses)
                    #
                    # # Reinitialize current dictionary.
                    # current_domain_to_ipv4_dict = dict()
                    # # Add domain and its ipv4 addresses.
                    # current_domain_to_ipv4_dict[question_domain] = ipv4_addresses_sorted
                    # # If the current dictionary is already not in the list:
                    # if current_domain_to_ipv4_dict not in known_a_records_domains_list_last_entries:
                    #     # Remove first entry if the list already contains
                    #     # 'known_records_number_of_entries' number of records.
                    #     if len(known_a_records_domains_list_last_entries) == known_records_number_of_entries:
                    #         known_a_records_domains_list_last_entries.pop(0)
                    #
                    #     # Add the dictionary to the list.
                    #     known_a_records_domains_list_last_entries.append(current_domain_to_ipv4_dict)
                    #
                    # dns.logger.info(f"Latest known list: {known_a_records_domains_list_last_entries}")

                    # ==================================================================================================
                    # Known domain list management (A Records only)

                    # If current request is in the cache,
                    # then the ipv4_addresses list will be the same as the previous time,
                    # so no need to check it at all.
                    if not dns_cached_request:
                        change_ipaddresses_and_dump_dictionary_to_file = False
                        # If IPv4 address list is not empty, meaning this DNS request was A type.
                        if ipv4_addresses:
                            # Check if current domain is already in known domains list that already hit the DNS server.
                            if question_domain in known_a_records_domains_dict:
                                # If so, get the list of current IPv4 addresses for that domain.
                                current_address_list = known_a_records_domains_dict[question_domain]

                                # Now iterate through all the received IPv4 addresses from current DNS request.
                                for new_address in ipv4_addresses:
                                    # If current new address is not in the known IPv4 addresses that we had from
                                    # previous DNS requests for the same domain name, then we'll add this address
                                    # to the known IPv4 address list for this domain.
                                    # And update the dictionary of known domains and their IPv4 addresses.
                                    if new_address not in current_address_list:
                                        current_address_list.append(new_address)
                                        known_a_records_domains_dict[question_domain] = current_address_list

                                        # Change the current IPv4 address list and dump this new list to a file.
                                        change_ipaddresses_and_dump_dictionary_to_file = True
                            # If the domain is not is the known records' dictionary, then we'll add it as is.
                            else:
                                # Put the new IPv4 list to current domain.
                                known_a_records_domains_dict[question_domain] = ipv4_addresses
                                # Change the current IPv4 address list and dump this new list to a file.
                                change_ipaddresses_and_dump_dictionary_to_file = True

                            # If we need to dump the dictionary to a file
                            # (this will happen only if new keys / values were added to dict)
                            if change_ipaddresses_and_dump_dictionary_to_file:
                                record_string_line = str()
                                for key, value in known_a_records_domains_dict.items():
                                    # Remove the brackets of the list object from the string.
                                    current_value = str(value).replace('[', '').replace(']', '')
                                    # Add current line to the existing one.
                                    record_string_line = f"{record_string_line}{key}: {current_value}\n"

                                # Save this string object as log file.
                                with open(
                                        self.log_directory_path + os.sep + self.known_domains_filename, 'w'
                                ) as output_file:
                                    output_file.write(record_string_line)

                                # self.logger.info(
                                #     f"Saved new known domains file: "
                                #     f"{self.log_directory_path}{os.sep}{self.known_domains_filename}")

                    # Known domain list managements EOF
                    # ==================================================================================================
                    # Known IPv4 address to domains list management (A Records only)

                    # If DNS Server 'offline_mode' was set to 'False'.
                    if not self.offline_mode:
                        dump_ipv4_dictionary_to_file = False
                        # If IPv4 address list is not empty, meaning this DNS request was A type.
                        if ipv4_addresses:
                            # Iterate through all the IPv4 addresses list of the current DNS request:
                            for ip_address_a_instance in ipv4_addresses:
                                current_ip_address = str(ip_address_a_instance)
                                # Check if current ipv4 is already in known ipv4
                                # addresses list that already hit the DNS server.
                                if current_ip_address in known_a_records_ipv4_dict:
                                    # If so, get the list of current domains for current ipv4 address.
                                    current_domains_list = known_a_records_ipv4_dict[current_ip_address]

                                    # If current question domain is not in the known domains that we had from
                                    # previous DNS requests for the same IPv4 address, then we'll add this domain
                                    # to the known domains list for this IPv4.
                                    # And update the dictionary of known IPv4 addresses and their domains.
                                    if question_domain not in current_domains_list:
                                        current_domains_list.append(question_domain)
                                        known_a_records_ipv4_dict[current_ip_address] = current_domains_list

                                        # And dump this new list to a file.
                                        dump_ipv4_dictionary_to_file = True
                                # If the IPv4 address is not is the "known records IPv4 dictionary",
                                # then we'll add it as is.
                                else:
                                    # It should be added as list, since this is what will be used if there are
                                    # more than one domain.
                                    current_domains_list = list()
                                    current_domains_list.append(question_domain)
                                    known_a_records_ipv4_dict[current_ip_address] = current_domains_list
                                    # And dump this new list to a file.
                                    dump_ipv4_dictionary_to_file = True

                                # If we need to dump the dictionary to a file
                                # (this will happen only if new keys / values were added to dict)
                                if dump_ipv4_dictionary_to_file:
                                    record_string_line = str()
                                    for key, value in known_a_records_ipv4_dict.items():
                                        # Remove the brackets of the list object from the string.
                                        current_value = str(value).replace('[', '').replace(']', '').replace('\'', '')
                                        # Add current line to the existing one.
                                        record_string_line = f"{record_string_line}{key}: {current_value}\n"

                                    # Save this string object as log file.
                                    with open(
                                            self.log_directory_path + os.sep + self.known_ipv4_filename, 'w'
                                    ) as output_file:
                                        output_file.write(record_string_line)

                                    # self.logger.info(
                                    #     f"Saved new known IPv4 addresses file: "
                                    #     f"{self.log_directory_path}{os.sep}{self.known_ipv4_filename}")

                    # Known IPv4 address to domains list management EOF
                    # ==================================================================================================
                    # Writing IPs by time.

                    # If IPv4 address list is not empty, meaning this DNS request was A type.
                    if ipv4_addresses:
                        for ip_address in ipv4_addresses:
                            current_time = datetime.datetime.now().strftime('%Y-%m-%d-%H:%M:%S')
                            record_string_line = f"{current_time} | {ip_address} | {question_domain}"

                            # Save this string object as log file.
                            with open(
                                    self.log_directory_path + os.sep + self.known_dns_ipv4_by_time_filename, 'a'
                            ) as output_file:
                                output_file.write(record_string_line + '\n')

                    # EOF Writing IPs by time.
                    # ==================================================================================================

                    # self.logger.info("==========")
                except Exception:
                    message = "Unknown Exception: to parse DNS request"
                    print_api(
                        message, logger=self.logger, logger_method='critical', traceback_string=True)
                    self.logger.info("==========")
                    pass
                    continue

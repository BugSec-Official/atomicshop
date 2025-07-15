from datetime import datetime
import threading
import queue
import socket

from ..wrappers.socketw import receiver, sender, socket_client, base
from .. import websocket_parse, ip_addresses
from ..http_parse import HTTPRequestParse, HTTPResponseParse
from ..basics import threads, tracebacks
from ..print_api import print_api

from .message import ClientMessage
from . import config_static, initialize_engines


def thread_worker_main(
        client_socket,
        process_commandline: str,
        is_tls: bool,
        tls_type: str,
        tls_version: str,
        domain_from_dns,
        network_logger,
        statistics_writer,
        engines_list,
        reference_module
):
    def output_statistics_csv_row(client_message: ClientMessage):
        # If there is no '.code' attribute in HTTPResponse, this means that this is not an HTTP message, so there is no
        # status code.
        try:
            http_status_code: str = str(client_message.response_auto_parsed.code)
        except AttributeError:
            http_status_code: str = str()

        # Same goes for the '.path' attribute, if it is not HTTP message then there will be no path.
        try:
            if client_message.request_auto_parsed and client_message.request_auto_parsed.path:
                http_path: str = client_message.request_auto_parsed.path
            elif client_message.response_auto_parsed.path:
                http_path: str = client_message.response_auto_parsed.path
            else:
                http_path: str = str()
        except AttributeError:
            http_path: str = str()

        # Same goes for the '.command' attribute, if it is not HTTP message then there will be no command.
        try:
            http_command: str = client_message.request_auto_parsed.command
        except AttributeError:
            http_command: str = str()

        if client_message.request_raw_bytes is None:
            request_size_bytes = ''
        else:
            request_size_bytes = str(len(client_message.request_raw_bytes))

        if client_message.response_raw_bytes is None:
            response_size_bytes = ''
        else:
            response_size_bytes = str(len(client_message.response_raw_bytes))

        if client_message.errors and len(client_message.errors) > 1:
            error_string = '||'.join(client_message.errors)
            error_string = f'Error count: {len(client_message.errors)} | Errors: {error_string}'
        elif client_message.errors and len(client_message.errors) == 1:
            error_string = client_message.errors[0]
        elif not client_message.errors:
            error_string = str()
        else:
            raise ValueError(f"Error in statistics error list. Values: {client_message.errors}")

        statistics_writer.write_row(
            thread_id=str(thread_id),
            engine=client_message.engine_name,
            source_host=client_message.client_name,
            source_ip=client_message.client_ip,
            tls_type=tls_type,
            tls_version=tls_version,
            protocol=client_message.protocol,
            protocol2=client_message.protocol2,
            protocol3=client_message.protocol3,
            dest_port=client_message.destination_port,
            host=client_message.server_name,
            path=http_path,
            status_code=http_status_code,
            command=http_command,
            timestamp=client_message.timestamp,
            request_size_bytes=request_size_bytes,
            response_size_bytes=response_size_bytes,
            recorded_file_path=client_message.recorded_file_path,
            process_cmd=process_commandline,
            action=client_message.action,
            error=error_string
        )

    def record_and_statistics_write(client_message: ClientMessage):
        # If recorder wasn't executed before, then execute it now
        if config_static.LogRec.enable_request_response_recordings_in_logs:
            recorded_file = recorder.record(class_client_message=client_message)
            client_message.recorded_file_path = recorded_file

        # Save statistics file.
        output_statistics_csv_row(client_message)

    def parse_http(
            raw_bytes: bytes,
            client_message: ClientMessage):
        nonlocal protocol

        # Parsing the raw bytes as HTTP.
        request_http_parsed, is_http_request, request_parsing_error = (
            HTTPRequestParse(raw_bytes).parse())

        response_http_parsed, is_http_response, response_parsing_error = (
            HTTPResponseParse(raw_bytes).parse())

        if is_http_request:
            if protocol == '':
                protocol = 'HTTP'

            auto_parsed = request_http_parsed
            network_logger.info(
                f"HTTP Request Parsed: Method: {request_http_parsed.command} | Path: {request_http_parsed.path}")
            http_path_queue.put(request_http_parsed.path)
            network_logger.info(f"HTTP Request Parsed: Putting PATH to queue.")

            is_http_request_a_websocket(auto_parsed, client_message)
        elif is_http_response:
            auto_parsed = response_http_parsed
            network_logger.info(
                f"HTTP Response Parsed: Status: {response_http_parsed.code}")

            auto_parsed.path = http_path_queue.get()
            network_logger.info(f"HTTP Response Parsed: Got PATH from queue: [{auto_parsed.path}]")
        elif protocol == 'Websocket':
            client_message.protocol2 = 'Frame'
            auto_parsed = parse_websocket(raw_bytes)
            if protocol3:
                client_message.protocol3 = protocol3
        else:
            auto_parsed = None

        return auto_parsed

    def is_http_request_a_websocket(
            auto_parsed,
            client_message: ClientMessage):
        nonlocal protocol
        nonlocal protocol3

        if protocol == 'HTTP':
            if auto_parsed and hasattr(auto_parsed, 'headers') and 'Upgrade' in auto_parsed.headers:
                if auto_parsed.headers['Upgrade'] == 'websocket':
                    protocol = 'Websocket'
                    client_message.protocol2 = 'Handshake'
                    protocol3 = auto_parsed.headers.get('Sec-WebSocket-Protocol', None)
                    if protocol3:
                        client_message.protocol3 = protocol3

                    network_logger.info(f'Protocol upgraded to Websocket')

    def parse_websocket(raw_bytes):
        return websocket_frame_parser.parse_frame_bytes(raw_bytes)

    def finish_thread():
        # At this stage there could be several times that the same socket was used to the service server - we need to
        # close this socket as well if it still opened.
        # The first part of the condition is to check if the service socket was connected at all.
        # If the service socket couldn't connect, then the instance will be None.
        if service_socket_instance and service_socket_instance.fileno() != -1:
            if service_client.socket_instance:
                service_client.close_socket()

        # If client socket is still opened - close
        if client_socket.fileno() != -1:
            client_socket.close()
            network_logger.info(f"Closed client socket [{client_ip}:{source_port}]...")

        network_logger.info("Thread Finished. Will continue listening on the Main thread")

    def create_requester_request(
            client_message: ClientMessage,
            sending_socket: socket.socket
    ) -> list[bytes]:
        request_custom_raw: bytes = requester.create_request(client_message, sending_socket=sending_socket)

        # Output first 100 characters of the request.
        requester.logger.info(f"{request_custom_raw[0: 100]}...")

        return [request_custom_raw]

    def create_responder_response(client_message: ClientMessage) -> list[bytes]:
        if client_message.action == 'service_connect':
            return responder.create_connect_response(client_message)
        else:
            # If we're in offline mode, and it's the first cycle and the protocol is Websocket, then we'll create the HTTP Handshake
            # response automatically.
            if config_static.MainConfig.offline and protocol == 'Websocket' and client_receive_count == 1:
                responses: list = list()
                responses.append(
                    websocket_parse.create_byte_http_response(client_message.request_raw_bytes))
            else:
                # Creating response for parsed message and printing
                responses: list = responder.create_response(client_message)

            # Output first 100 characters of all the responses in the list.
            for response_raw_bytes_single in responses:
                responder.logger.info(f"{response_raw_bytes_single[0: 100]}...")

            return responses

    def create_client_socket(client_message: ClientMessage):
        # If there is a custom certificate for the client for this domain, then we'll use it.
        # noinspection PyTypeChecker
        custom_client_pem_certificate_path: str = None
        for subdomain, pem_file_path in found_domain_module.mtls.items():
            if subdomain == client_message.server_name:
                custom_client_pem_certificate_path = pem_file_path
                break

        # Check if the destination service is an ip address or a domain name.
        if ip_addresses.is_ip_address(client_message.server_name, ip_type='ipv4'):
            # If it's an ip address, connect to the ip address directly.
            service_client_instance = socket_client.SocketClient(
                service_name=client_message.server_name,
                connection_ip=client_message.server_name,
                service_port=client_message.destination_port,
                tls=is_tls,
                logger=network_logger,
                custom_pem_client_certificate_file_path=custom_client_pem_certificate_path,
                enable_sslkeylogfile_env_to_client_ssl_context=(
                    config_static.Certificates.enable_sslkeylogfile_env_to_client_ssl_context)
            )
        # If it's a domain name, then we'll use the DNS to resolve it.
        else:
            # If we're on localhost, then use external services list in order to resolve the domain:
            # config['tcp']['forwarding_dns_service_ipv4_list___only_for_localhost']
            if client_message.client_ip in base.THIS_DEVICE_IP_LIST:
                service_client_instance = socket_client.SocketClient(
                    service_name=client_message.server_name,
                    service_port=client_message.destination_port,
                    tls=is_tls,
                    dns_servers_list=[config_static.DNSServer.forwarding_dns_service_ipv4],
                    logger=network_logger,
                    custom_pem_client_certificate_file_path=custom_client_pem_certificate_path,
                    enable_sslkeylogfile_env_to_client_ssl_context=(
                        config_static.Certificates.enable_sslkeylogfile_env_to_client_ssl_context)
                )
            # If we're not on localhost, then connect to domain directly.
            else:
                service_client_instance = socket_client.SocketClient(
                    service_name=client_message.server_name,
                    service_port=client_message.destination_port,
                    tls=is_tls,
                    logger=network_logger,
                    custom_pem_client_certificate_file_path=custom_client_pem_certificate_path,
                    enable_sslkeylogfile_env_to_client_ssl_context=(
                        config_static.Certificates.enable_sslkeylogfile_env_to_client_ssl_context)
                )

        return service_client_instance

    def process_client_raw_data(
            client_received_raw_data: bytes,
            error_string: str,
            client_message: ClientMessage):
        """
        Process the client raw data request.
        """
        nonlocal protocol

        client_message.request_raw_bytes = client_received_raw_data

        if error_string:
            client_message.errors.append(error_string)

        if client_received_raw_data == b'' or client_received_raw_data is None:
            return

        client_message.request_auto_parsed = parse_http(client_message.request_raw_bytes, client_message)
        # This is needed for each cycle that is not HTTP, but its protocol maybe set by HTTP, like websocket.
        if protocol != '':
            client_message.protocol = protocol

        # Parse websocket frames only if it is not the first protocol upgrade request.
        if protocol == 'Websocket' and client_receive_count != 1:
            client_message.request_auto_parsed = parse_websocket(client_message.request_raw_bytes)

        # Custom parser, should parse HTTP body or the whole message if not HTTP.
        parser_instance = parser(client_message)
        parser_instance.parse()

        # Converting body parsed to string on logging, there is no strict rule for the parameter to be string.
        parser_instance.logger.info(f"{str(client_message.request_custom_parsed)[0: 100]}...")

    def process_server_raw_data(
            service_received_raw_data: bytes,
            error_string: str,
            client_message: ClientMessage
    ):
        nonlocal protocol

        client_message.response_raw_bytes = service_received_raw_data

        if error_string:
            client_message.errors.append(error_string)

        if service_received_raw_data == b'' or service_received_raw_data is None:
            return

        client_message.response_auto_parsed = parse_http(client_message.response_raw_bytes, client_message)
        if protocol != '':
            client_message.protocol = protocol

    def client_message_first_start() -> ClientMessage:
        client_message: ClientMessage = ClientMessage()
        client_message.client_name = client_name
        client_message.client_ip = client_ip
        client_message.server_ip = server_ip
        client_message.source_port = source_port
        client_message.destination_port = destination_port
        client_message.server_name = server_name
        client_message.thread_id = thread_id
        client_message.process_name = process_commandline
        client_message.engine_name = engine_name

        return client_message

    def receive_send_start(
            receiving_socket,
            sending_socket = None,
            exception_queue: queue.Queue = None,
            client_connection_message: ClientMessage = None
    ):
        nonlocal client_receive_count
        nonlocal server_receive_count
        nonlocal exception_or_close_in_receiving_thread

        # Set the thread name to the custom name for logging
        # threading.current_thread().name = thread_name

        # Initialize the client message object with current thread's data.
        client_message: ClientMessage = client_message_first_start()

        try:
            if receiving_socket is client_socket:
                side: str = 'Client'
            elif receiving_socket is service_socket_instance:
                side: str = 'Service'
            else:
                raise ValueError(f"Unknown side of the socket: {receiving_socket}")

            while True:
                is_socket_closed: bool = False
                # pass the socket connect to responder.
                if side == 'Service' and client_connection_message:
                    client_message = client_connection_message

                    bytes_to_send_list: list[bytes] = create_responder_response(client_message)
                    print_api(f"Got responses from connect responder, count: [{len(bytes_to_send_list)}]", logger=network_logger,
                              logger_method='info')

                    received_raw_data = None
                else:
                    client_message.reinitialize_dynamic_vars()

                    if side == 'Client':
                        client_receive_count += 1
                        current_count = client_receive_count
                    else:
                        server_receive_count += 1
                        current_count = server_receive_count

                    # Getting current time of message received, either from client or service.
                    client_message.timestamp = datetime.now()

                    # # No need to receive on service socket if we're in offline mode, because there is no service to connect to.
                    # if config_static.MainConfig.offline and side == 'Service':
                    #     print_api("Offline Mode, skipping receiving on service socket.", logger=network_logger,
                    #               logger_method='info')
                    # else:

                    network_logger.info(
                        f"Initializing Receiver for {side} cycle: {str(current_count)}")

                    # Getting message from the client over the socket using specific class.
                    received_raw_data, is_socket_closed, error_message = receiver.Receiver(
                        ssl_socket=receiving_socket, logger=network_logger).receive()

                    # In case of client socket, we'll process the raw data specifically for the client.
                    if side == 'Client':
                        process_client_raw_data(received_raw_data, error_message, client_message)
                        client_message.action = 'client_receive'
                    # In case of service socket, we'll process the raw data specifically for the service.
                    else:
                        process_server_raw_data(received_raw_data, error_message, client_message)
                        client_message.action = 'service_receive'

                    # If there was an exception in the service thread, then receiving empty bytes doesn't mean that
                    # the socket was closed by the other side, it means that the service thread closed the socket.
                    if (received_raw_data == b'' or error_message) and exception_or_close_in_receiving_thread:
                        print_api("Both sockets are closed, breaking the loop", logger=network_logger,
                                  logger_method='info')
                        return

                    # We will record only if there was no closing signal, because if there was, it means that we initiated
                    # the close on the opposite socket.
                    record_and_statistics_write(client_message)

                    # if is_socket_closed:
                    #     exception_or_close_in_receiving_thread = True
                    #     finish_thread()
                    #     return

                    # Now send it to requester/responder.
                    if side == 'Client':
                        # Send to requester.
                        bytes_to_send_list: list[bytes] = create_requester_request(
                            client_message, sending_socket=sending_socket)

                        # If we're in offline mode, then we'll put the request to the responder right away.
                        if config_static.MainConfig.offline:
                            print_api("Offline Mode, sending to responder directly.", logger=network_logger,
                                      logger_method='info')
                            process_client_raw_data(bytes_to_send_list[0], error_message, client_message)
                            bytes_to_send_list = create_responder_response(client_message)
                    elif side == 'Service':
                        bytes_to_send_list: list[bytes] = create_responder_response(client_message)
                        print_api(f"Got responses from responder, count: [{len(bytes_to_send_list)}]",
                                  logger=network_logger,
                                  logger_method='info')
                    else:
                        raise ValueError(f"Unknown side [{side}] of the socket: {receiving_socket}")


                # If nothing was passed from the responder, and the client message is the connection message, then we'll skip to the next iteration.
                if not bytes_to_send_list and client_connection_message:
                    client_connection_message = None
                    continue

                # is_socket_closed: bool = False
                error_on_send: str = str()
                for bytes_to_send_single in bytes_to_send_list:
                    client_message.reinitialize_dynamic_vars()
                    client_message.timestamp = datetime.now()

                    if side == 'Client':
                        client_message.request_raw_bytes = bytes_to_send_single
                    else:
                        client_message.response_raw_bytes = bytes_to_send_single

                    # This records the requester or responder output, only if it is not the same as the original
                    # message.
                    if bytes_to_send_single != received_raw_data:
                        if side == 'Client':
                            client_message.action = 'client_requester'

                            if config_static.MainConfig.offline:
                                client_message.action = 'client_responder_offline'
                        elif side == 'Service':
                            client_message.action = 'service_responder'
                        record_and_statistics_write(client_message)

                    # If we're in offline mode, it means we're in the client thread, and we'll send the
                    # bytes back to the client socket.
                    if config_static.MainConfig.offline:
                        error_on_send: str = sender.Sender(
                            ssl_socket=receiving_socket, class_message=bytes_to_send_single,
                            logger=network_logger).send()
                    else:
                        error_on_send: str = sender.Sender(
                            ssl_socket=sending_socket, class_message=bytes_to_send_single,
                            logger=network_logger).send()

                    if error_on_send:
                        client_message.reinitialize_dynamic_vars()
                        client_message.errors.append(error_on_send)
                        client_message.timestamp = datetime.now()
                        if side == 'Client':
                            client_message.action = 'service_send'
                        else:
                            client_message.action = 'client_send'

                        record_and_statistics_write(client_message)

                # If the socket was closed on message receive, then we'll break the loop only after send.
                if is_socket_closed or error_on_send:
                    exception_or_close_in_receiving_thread = True
                    finish_thread()
                    return

                # For next iteration to start in case this iteration was responsible to process connection message, we need to set it to None.
                client_connection_message = None
        except Exception as exc:
            # If the sockets were already closed, then there is nothing to do here besides log.
            # if (isinstance(exc, OSError) and exc.errno == 10038 and
            #         client_socket.fileno() == -1 and service_socket_instance.fileno() == -1):
            if isinstance(exc, OSError) and exc.errno == 10038:
                print_api("Both sockets are closed, breaking the loop", logger=network_logger, logger_method='info')
            else:
                handle_exceptions_on_sub_connection_thread(client_message, exception_queue, exc)

    def handle_exceptions_on_sub_connection_thread(
            client_message: ClientMessage,
            exception_queue: queue.Queue,
            exc: Exception
    ):
        nonlocal exception_or_close_in_receiving_thread

        exception_or_close_in_receiving_thread=True
        # handle_exceptions(exc, client_message, recorded)
        exception_message = tracebacks.get_as_string(one_line=True)

        error_message = f'Socket Thread [{str(thread_id)}] Exception: {exception_message}'
        print_api("Exception in a thread, forwarding to parent thread.", logger_method='info', logger=network_logger)
        client_message.errors.append(error_message)

        # if not recorded:
        #     record_and_statistics_write(client_message)

        finish_thread()
        exception_queue.put(exc)

    def handle_exceptions_on_main_connection_thread(
            exc: Exception,
            client_message: ClientMessage
    ):
        exception_message = tracebacks.get_as_string(one_line=True)
        error_message = f'Socket Thread [{str(thread_id)}] Exception: {exception_message}'
        print_api(error_message, logger_method='critical', logger=network_logger)
        client_message.errors.append(error_message)

        # === At this point while loop of 'client_connection_boolean' was broken =======================================
        # If recorder wasn't executed before, then execute it now
        record_and_statistics_write(client_message)

        finish_thread()

        # After the socket clean up, we will still raise the exception to the main thread.
        raise exc

    # ================================================================================================================
    # This is the start of the thread_worker_main function

    # Only protocols that are encrypted with TLS have the server name attribute.
    if is_tls:
        # Get current destination domain
        server_name = client_socket.server_hostname
    # If the protocol is not TLS, then we'll use the domain from the DNS.
    else:
        server_name = domain_from_dns

    thread_id = threads.current_thread_id()

    # This is the main protocols.
    protocol: str = str()
    # This is the secondary protocol in the websocket.
    protocol3: str = str()
    # # This is Client Masked Frame Parser.
    # websocket_masked_frame_parser = websocket_parse.WebsocketFrameParser()
    # # This is Server UnMasked Frame Parser.
    # websocket_unmasked_frame_parser = websocket_parse.WebsocketFrameParser()
    websocket_frame_parser = websocket_parse.WebsocketFrameParser()

    # Loading parser by domain, if there is no parser for current domain - general reference parser is loaded.
    # These should be outside any loop and initialized only once entering the thread.
    found_domain_module = initialize_engines.assign_class_by_domain(
        engines_list=engines_list,
        message_domain_name=server_name,
        reference_module=reference_module
    )
    parser = found_domain_module.parser_class_object
    requester = found_domain_module.requester_class_object()
    responder = found_domain_module.responder_class_object()
    recorder = found_domain_module.recorder_class_object(record_path=config_static.LogRec.recordings_path)

    network_logger.info(f"Assigned Modules for [{server_name}]: "
        f"{parser.__name__}, "
        f"{requester.__class__.__name__}, "
        f"{responder.__class__.__name__}, "
        f"{recorder.__class__.__name__}")

    # Initializing the client message object with current thread's data.
    # This is needed only to skip error alerts after 'try'.
    client_message_connection: ClientMessage = ClientMessage()
    # This is needed to indicate if there was an exception or socket was closed in any of the receiving thread.
    exception_or_close_in_receiving_thread: bool = False
    # Queue for http request URI paths.
    http_path_queue: queue.Queue = queue.Queue()

    try:
        engine_name: str = recorder.engine_name
        client_ip, source_port = client_socket.getpeername()
        client_name: str = socket.gethostbyaddr(client_ip)[0]
        destination_port: int = client_socket.getsockname()[1]
        destination_port_str: str = str(destination_port)

        # If the destination port is in the on_port_connect dictionary, then we'll get the port from there.
        if destination_port_str in found_domain_module.on_port_connect:
            on_port_connect_value = found_domain_module.on_port_connect[destination_port_str]
            _, destination_port_str = initialize_engines.get_ipv4_from_engine_on_connect_port(on_port_connect_value)
            destination_port: int = int(destination_port_str)

        if config_static.MainConfig.offline:
            # If in offline mode, then we'll get the TCP server's input address.
            server_ip = client_socket.getsockname()[0]
        else:
            # If not in offline mode, we will get the ip from the socket that will connect later to the service.
            server_ip = ""

        network_logger.info(f"Thread Created - Client [{client_ip}:{source_port}] | "
                            f"Destination service: [{server_name}:{destination_port}]")

        service_client = None
        client_receive_count: int = 0
        server_receive_count: int = 0
        client_message_connection = client_message_first_start()

        # If we're not in offline mode, then we'll create the client socket to the service.
        # noinspection PyTypeChecker
        connection_error: str = None
        service_socket_instance = None
        client_message_connection.action = 'service_connect'
        client_message_connection.timestamp = datetime.now()

        if config_static.MainConfig.offline:
            client_message_connection.info = 'Offline Mode'
        else:
            service_client = create_client_socket(client_message_connection)
            service_socket_instance, connection_error = service_client.service_connection()

            if connection_error:
                client_message_connection.errors.append(connection_error)
                record_and_statistics_write(client_message_connection)
            else:
                # Now we'll update the server IP with the IP of the service.
                server_ip = service_socket_instance.getpeername()[0]
                client_message_connection.server_ip = server_ip

        if not connection_error:
            client_exception_queue: queue.Queue = queue.Queue()
            client_thread = threading.Thread(
                target=receive_send_start,
                args=(client_socket, service_socket_instance, client_exception_queue, None),
                name=f"Thread-{thread_id}-Client",
                daemon=True)
            client_thread.start()

            service_exception_queue: queue.Queue = queue.Queue()
            if not config_static.MainConfig.offline:
                service_thread = threading.Thread(
                    target=receive_send_start,
                    args=(service_socket_instance, client_socket, service_exception_queue, client_message_connection),
                    name=f"Thread-{thread_id}-Service",
                    daemon=True)
                service_thread.start()

            client_thread.join()
            # If we're in offline mode, then there is no service thread.
            if not config_static.MainConfig.offline:
                # If we're not in offline mode, then we'll wait for the service thread to finish.
                # noinspection PyUnboundLocalVariable
                service_thread.join()

            # If there was an exception in any of the threads, then we'll raise it here.
            if not client_exception_queue.empty():
                raise client_exception_queue.get()
            if not service_exception_queue.empty():
                raise service_exception_queue.get()

        finish_thread()
    except Exception as e:
        handle_exceptions_on_main_connection_thread(e, client_message_connection)

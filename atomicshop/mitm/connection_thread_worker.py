from datetime import datetime

from ..wrappers.socketw import receiver, sender, socket_client, base
from .. import websocket_parse
from ..http_parse import HTTPRequestParse, HTTPResponseParse
from ..basics import threads, tracebacks
from ..print_api import print_api

from .message import ClientMessage
from .initialize_engines import assign_class_by_domain
from . import config_static


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
    def output_statistics_csv_row():
        # If there is no '.code' attribute in HTTPResponse, this means that this is not an HTTP message, so there is no
        # status code.
        try:
            http_status_code: str = ','.join([str(x.code) for x in client_message.response_list_of_raw_decoded])
        except AttributeError:
            http_status_code: str = str()

        # Same goes for the '.path' attribute, if it is not HTTP message then there will be no path.
        try:
            http_path: str = client_message.request_raw_decoded.path
        except AttributeError:
            http_path: str = str()

        # Same goes for the '.command' attribute, if it is not HTTP message then there will be no command.
        try:
            http_command: str = client_message.request_raw_decoded.command
        except AttributeError:
            http_command: str = str()

        response_size_bytes: str = str()
        for response_index, response in enumerate(client_message.response_list_of_raw_bytes):
            if response is None:
                response_size_bytes += ''
            else:
                response_size_bytes += str(len(response))

            # If it is not the last entry, add the comma.
            if response_index + 1 != len(client_message.response_list_of_raw_bytes):
                response_size_bytes += ','

        # response_size_bytes = ','.join([str(len(x)) for x in client_message.response_list_of_raw_bytes])

        if statistics_error_list and len(statistics_error_list) > 1:
            error_string = '||'.join(statistics_error_list)
        elif statistics_error_list and len(statistics_error_list) == 1:
            error_string = statistics_error_list[0]
        elif not statistics_error_list:
            error_string = str()
        else:
            raise ValueError(f"Error in statistics error list. Values: {statistics_error_list}")

        statistics_writer.write_row(
            thread_id=str(thread_id),
            host=client_message.server_name,
            tls_type=tls_type,
            tls_version=tls_version,
            protocol=client_message.protocol,
            path=http_path,
            status_code=http_status_code,
            command=http_command,
            request_time_sent=client_message.request_time_received,
            request_size_bytes=len(client_message.request_raw_bytes),
            response_size_bytes=response_size_bytes,
            recorded_file_path=client_message.recorded_file_path,
            process_cmd=process_commandline,
            error=error_string
        )

    def record_and_statistics_write():
        # If recorder wasn't executed before, then execute it now
        if config_static.LogRec.enable_request_response_recordings_in_logs:
            recorded_file = recorder(
                class_client_message=client_message, record_path=config_static.LogRec.recordings_path).record()
            client_message.recorded_file_path = recorded_file

        # Save statistics file.
        output_statistics_csv_row()

    def parse_http():
        nonlocal error_message
        nonlocal protocol
        # Parsing the raw bytes as HTTP.
        request_decoded, is_http_request, request_parsing_info, request_parsing_error = (
            HTTPRequestParse(client_message.request_raw_bytes).parse())

        if is_http_request:
            if protocol == '':
                protocol = 'HTTP'

            client_message.request_raw_decoded = request_decoded
            print_api(request_parsing_info, logger=network_logger, logger_method='info')
            network_logger.info(f"Method: {request_decoded.command} | Path: {request_decoded.path}")
        else:
            # It doesn't matter if we have HTTP Parsing error, since the request may not be really HTTP, so it is OK
            # not to log it into statistics.
            # statistics_error_list.append(error_message)
            print_api(request_parsing_error, logger=network_logger, logger_method='error', color='yellow')

        is_http_request_a_websocket()

    def is_http_request_a_websocket():
        nonlocal protocol

        if protocol == 'HTTP':
            if (client_message.request_raw_decoded and
                    hasattr(client_message.request_raw_decoded, 'headers') and
                    'Upgrade' in client_message.request_raw_decoded.headers):
                if client_message.request_raw_decoded.headers['Upgrade'] == 'websocket':
                    protocol = 'Websocket'

                    network_logger.info(f'Protocol upgraded to Websocket')

    def parse_websocket(raw_bytes):
        return websocket_frame_parser.parse_frame_bytes(raw_bytes)

    def finish_thread():
        # At this stage there could be several times that the same socket was used to the service server - we need to
        # close this socket as well if it still opened.
        if service_client:
            if service_client.socket_instance:
                service_client.close_socket()

        # If client socket is still opened - close
        if client_socket:
            client_socket.close()
            network_logger.info(f"Closed client socket [{client_message.client_ip}:{client_message.source_port}]...")

        network_logger.info("Thread Finished. Will continue listening on the Main thread")

    # Building client message object before the loop only for any exception to occurs, since we write it to
    # recording file in its current state.
    client_message: ClientMessage = ClientMessage()
    # 'recorded' boolean is needed only to write the message in case of exception in the loop or before that.
    recorded: bool = False
    statistics_error_list: list[str] = list()

    # Only protocols that are encrypted with TLS have the server name attribute.
    if is_tls:
        # Get current destination domain
        server_name = client_socket.server_hostname
        # client_message.server_name = domain_from_dns
    # If the protocol is not TLS, then we'll use the domain from the DNS.
    else:
        server_name = domain_from_dns
    client_message.server_name = server_name

    thread_id = threads.current_thread_id()
    client_message.thread_id = thread_id

    protocol: str = str()
    # # This is Client Masked Frame Parser.
    # websocket_masked_frame_parser = websocket_parse.WebsocketFrameParser()
    # # This is Server UnMasked Frame Parser.
    # websocket_unmasked_frame_parser = websocket_parse.WebsocketFrameParser()
    websocket_frame_parser = websocket_parse.WebsocketFrameParser()

    # Loading parser by domain, if there is no parser for current domain - general reference parser is loaded.
    # These should be outside any loop and initialized only once entering the thread.
    parser, responder, recorder = assign_class_by_domain(
        engines_usage=config_static.TCPServer.engines_usage,
        engines_list=engines_list,
        message_domain_name=server_name,
        reference_module=reference_module,
        logger=network_logger
    )

    try:
        client_ip, source_port = client_socket.getpeername()
        client_message.client_ip = client_ip
        client_message.source_port = source_port

        destination_port = client_socket.getsockname()[1]
        client_message.destination_port = destination_port

        network_logger.info(f"Thread Created - Client [{client_ip}:{source_port}] | "
                            f"Destination service: [{server_name}:{destination_port}]")

        service_client = None
        # Loop while received message is not empty, if so, close socket, since other side already closed.
        # noinspection PyTypeChecker
        cycle_count: int = None
        while True:
            # If cycle count is None, then it's the first cycle, else it's not.
            # The cycle_count should be added 1 in the beginning of each cycle, and not in the end, since not always
            # the cycle will be executed till the end.
            if cycle_count is None:
                cycle_count = 0
            else:
                cycle_count += 1

            recorded: bool = False
            statistics_error_list: list[str] = list()

            client_message = ClientMessage()
            client_message.thread_id = thread_id
            client_message.client_ip = client_ip
            client_message.source_port = source_port
            client_message.destination_port = destination_port
            client_message.process_name = process_commandline
            client_message.server_name = server_name
            # Getting current time of message received from client.
            client_message.request_time_received = datetime.now()

            network_logger.info(f"Initializing Receiver on cycle: {str(cycle_count+1)}")
            # Getting message from the client over the socket using specific class.
            client_received_raw_data = receiver.Receiver(
                ssl_socket=client_socket, logger=network_logger).receive()

            # If the message is empty, then the connection was closed already by the other side,
            # so we can close the socket as well.
            # If the received message from the client is not empty, then continue.
            if client_received_raw_data:
                # Putting the received message to the aggregating message class.
                client_message.request_raw_bytes = client_received_raw_data

                parse_http()
                if protocol != '':
                    client_message.protocol = protocol

                # Parse websocket frames only if it is not the first protocol upgrade request.
                if protocol == 'Websocket' and cycle_count != 0:
                    client_message.request_raw_decoded = parse_websocket(client_message.request_raw_bytes)

                # Custom parser, should parse HTTP body or the whole message if not HTTP.
                parser_instance = parser(client_message)
                parser_instance.parse()

                # Converting body parsed to string on logging, since there is no strict rule for the parameter
                # to be string.
                parser_instance.logger.info(f"{str(client_message.request_body_parsed)[0: 100]}...")

                # If we're in response mode, execute responder.
                response_raw_bytes = None
                if config_static.TCPServer.server_response_mode:
                    # Since we're in response mode, we'll record the request anyway, after the responder did its job.
                    client_message.info = "In Server Response Mode"

                    # Re-initiate the 'client_message.response_list_of_raw_bytes' list, since we'll be appending
                    # new entries for empty list.
                    client_message.response_list_of_raw_bytes = list()

                    # If it's the first cycle and the protocol is Websocket, then we'll create the HTTP Handshake
                    # response automatically.
                    if protocol == 'Websocket' and cycle_count == 0:
                        client_message.response_list_of_raw_bytes.append(
                            websocket_parse.create_byte_http_response(client_message.request_raw_bytes))
                    # Creating response for parsed message and printing
                    responder.create_response(client_message)

                    # Output first 100 characters of all the responses in the list.
                    for response_raw_bytes in client_message.response_list_of_raw_bytes:
                        if response_raw_bytes:
                            responder.logger.info(f"{response_raw_bytes[0: 100]}...")
                        else:
                            responder.logger.info(f"Response empty...")
                # Else, we're not in response mode, then execute client connect and record section.
                else:
                    # If "service_client" object is not defined, we'll define it.
                    # If it's defined, then it means there's still active "ssl_socket" with connection to the service
                    # domain.
                    if not service_client:
                        # If we're on localhost, then use external services list in order to resolve the domain:
                        # config['tcp']['forwarding_dns_service_ipv4_list___only_for_localhost']
                        if client_message.client_ip in base.THIS_DEVICE_IP_LIST:
                            service_client = socket_client.SocketClient(
                                service_name=client_message.server_name, service_port=client_message.destination_port,
                                tls=is_tls,
                                dns_servers_list=(
                                    config_static.TCPServer.forwarding_dns_service_ipv4_list___only_for_localhost),
                                logger=network_logger
                            )
                        # If we're not on localhost, then connect to domain directly.
                        else:
                            service_client = socket_client.SocketClient(
                                service_name=client_message.server_name, service_port=client_message.destination_port,
                                tls=is_tls, logger=network_logger)

                    # Sending current client message and receiving a response.
                    # If there was an error it will be passed to "client_message" object class and if not, "None" will
                    # be passed.
                    # If there was connection error or socket close, then "ssl_socket" of the "service_client"
                    # will be empty.
                    response_raw_bytes, client_message.error, client_message.server_ip, service_ssl_socket = (
                        service_client.send_receive_to_service(client_message.request_raw_bytes))

                    if client_message.error is not None:
                        statistics_error_list.append(client_message.error)

                    # Since we need a list for raw bytes, we'll add the 'response_raw_bytes' to our list object.
                    # But we need to re-initiate it first.
                    client_message.response_list_of_raw_bytes = list()
                    # If there was error during send or receive from the service and response was None,
                    # It means that there was no response at all because of the error.
                    if client_message.error and response_raw_bytes is None:
                        client_message.response_list_of_raw_bytes.append(None)
                    # If there was no error, but response came empty, it means that the service has closed the
                    # socket after it received the request, without sending any data.
                    elif client_message.error is None and response_raw_bytes is None:
                        client_message.response_list_of_raw_bytes.append("")
                    else:
                        client_message.response_list_of_raw_bytes.append(response_raw_bytes)

                    client_message.response_list_of_raw_decoded = list()
                    # Make HTTP Response parsing only if there was response at all.
                    if response_raw_bytes:
                        response_raw_decoded, is_http_response, response_parsing_error = (
                            HTTPResponseParse(response_raw_bytes).parse())

                        if is_http_response:
                            client_message.response_list_of_raw_decoded.append(response_raw_decoded)
                        elif protocol == 'Websocket' and cycle_count != 0:
                            response_decoded = parse_websocket(response_raw_bytes)
                            client_message.response_list_of_raw_decoded.append(response_decoded)
                        else:
                            client_message.response_list_of_raw_decoded.append(None)



                    # So if the socket was closed and there was an error we can break the loop
                    if not service_ssl_socket:
                        record_and_statistics_write()
                        recorded = True
                        break

                # If there is a response, then send it.
                if response_raw_bytes:
                    # Sending response/s to client no matter if in record mode or not.
                    network_logger.info(
                        f"Sending messages to client: {len(client_message.response_list_of_raw_bytes)}")

                    # Iterate through the list of byte responses.
                    for response_raw_bytes in client_message.response_list_of_raw_bytes:
                        error_on_send: str = sender.Sender(
                            ssl_socket=client_socket, class_message=response_raw_bytes,
                            logger=network_logger).send()

                        # If there was problem with sending data, we'll break current loop.
                        if error_on_send:
                            statistics_error_list.append(error_on_send)
                            break
                # If response from server came back empty, then the server has closed the connection,
                # we will do the same.
                else:
                    network_logger.info(f"Response empty, nothing to send to client.")
                    break

                record_and_statistics_write()
                recorded = True
            else:
                # If it's the first cycle we will record the message from the client if it came empty.
                if cycle_count == 0:
                    record_and_statistics_write()

                # In other cases, we'll just break the loop, since empty message means that the other side closed the
                # connection.
                recorded = True
                break

        finish_thread()
    except Exception as e:
        exception_message = tracebacks.get_as_string(one_line=True)
        error_message = f'Socket Thread [{str(thread_id)}] Exception: {exception_message}'
        print_api(error_message, logger_method='critical', logger=network_logger)
        statistics_error_list.append(error_message)

        # === At this point while loop of 'client_connection_boolean' was broken =======================================
        # If recorder wasn't executed before, then execute it now
        if not recorded:
            record_and_statistics_write()

        finish_thread()

        # After the socket clean up, we will still raise the exception to the main thread.
        raise e

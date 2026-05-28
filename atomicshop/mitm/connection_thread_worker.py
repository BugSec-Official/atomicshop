import multiprocessing
from datetime import datetime
import threading
import queue
import socket
import ssl
from typing import Literal
import struct

from ..wrappers.socketw import receiver, sender, socket_client, socket_base
from ..wrappers.socketw.framers import (
    Framer, Http11Framer, Http2Framer, MqttFramer, ProtocolSniffer,
    SharedProtocolState, WebSocketFramer)
from .. import ip_addresses
from ..wrappers.protocol_parsers import websocket
from ..wrappers.protocol_parsers.http import HTTPRequestParse, HTTPResponseParse
from ..wrappers.protocol_parsers.http2 import Http2DirectionParser, Http2RequestParse, Http2ResponseParse
from ..wrappers.protocol_parsers.mqtt import MqttConnectionState, MqttDirectionParser
from ..basics import threads, tracebacks
from ..print_api import print_api

from .message import ClientMessage
from . import initialize_engines
from ..wrappers.loggingw import loggingw
# This is needed only for the data typing.
from . import config_static as cf


def thread_worker_main(
        # These parameters come from the SocketWrapper.
        client_socket,
        process_commandline: str,
        is_tls: bool,
        tls_type: str,
        tls_version: str,
        domain_from_dns,
        statistics_writer,
        engines_list: list[initialize_engines.ModuleCategory],
        client_alpn_offers: list[str] | None,

        # These parameters come from the main mitm module.
        config_static: cf
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
            client_message: ClientMessage,
            side: str = 'Client'):
        nonlocal protocol
        nonlocal h2_request_parser
        nonlocal h2_response_parser
        nonlocal mqtt_request_parser
        nonlocal mqtt_response_parser

        # MQTT short-circuit: ALPN='mqtt' selects MqttFramer which yields one
        # control packet at a time. Skip HTTP parsing entirely on this leg.
        mqtt_parser = mqtt_request_parser if side == 'Client' else mqtt_response_parser
        if mqtt_parser is not None:
            if protocol == '':
                protocol = 'MQTT'
            auto_parsed = None
            for msg in mqtt_parser.feed(raw_bytes):
                auto_parsed = msg
                if msg.error:
                    network_logger.warning(
                        f"MQTT {msg.packet_type or 'parse'} error: {msg.error}")
                else:
                    network_logger.info(
                        f"MQTT {msg.packet_type} parsed: "
                        f"qos={msg.qos} topic={msg.topic!r} "
                        f"client_id={msg.client_id!r} pid={msg.packet_identifier} "
                        f"(v{msg.protocol_version})")
            return auto_parsed

        # HTTP/2 short-circuit: per-direction h2 state lives in this closure.
        # The framer hands over raw bytes; the autoparser feeds them through
        # h2.H2Connection and yields one parsed object per StreamEnded.
        h2_parser = h2_request_parser if side == 'Client' else h2_response_parser
        if h2_parser is not None:
            if protocol == '':
                protocol = 'HTTP/2'
            auto_parsed = None
            for msg in h2_parser.feed(raw_bytes):
                auto_parsed = msg
                if isinstance(msg, Http2RequestParse):
                    http_path_queue.put(msg.path)
                    network_logger.info(
                        f"HTTP/2 Request Parsed: Method: {msg.command} | Path: {msg.path} "
                        f"(stream {msg.stream_id})")
                else:
                    # Only correlate path for final responses; 1xx interims share the stream
                    # with the final response and shouldn't consume the path queue entry.
                    if msg.code >= 200:
                        try:
                            msg.path = http_path_queue.get_nowait()
                        except queue.Empty:
                            pass
                    network_logger.info(
                        f"HTTP/2 Response Parsed: Status: {msg.code} (stream {msg.stream_id})")
            return auto_parsed

        # Parsing the raw bytes as HTTP.
        request_http_parsed, is_http_request, request_parsing_error = (
            HTTPRequestParse(raw_bytes).parse())

        response_http_parsed, is_http_response, response_parsing_error = (
            HTTPResponseParse(raw_bytes).parse())

        if is_http_request:
            if protocol == '':
                protocol = request_http_parsed.request_version  # 'HTTP/1.0' | 'HTTP/1.1' from h11

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

            # 1xx interims (100/101/103) don't complete the request/response cycle —
            # the next final response (>=200) pops the path. Without this guard, a 1xx
            # would steal the path and the final response would block on .get().
            if response_http_parsed.code >= 200:
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
        try:
            return websocket_frame_parser.parse_frame_bytes(raw_bytes)
        except Exception as e:
            network_logger.warning(f"Failed to parse websocket frame: {e}")
            return None

    def _push_request_method_fifo(method: str):
        """FIFO the request method to the service's response framer for HEAD elision."""
        if not method:
            return
        service_recv = side_receivers.get('Service')
        framer = service_recv._framer if service_recv is not None else None
        # Http11Framer + HttpFramer (wrapping s2c Http11Framer) accept this; other
        # framers (Http2/MQTT/WebSocket) don't and are skipped by the hasattr guard.
        if framer is not None and hasattr(framer, 'set_pending_request_method'):
            framer.set_pending_request_method(method)

    def finish_thread(send_connection_reset: bool = False):
        """
        Finishing the thread, closing sockets.

        :param send_connection_reset: Whether to send TCP RST flag to the client when closing the socket.
            Basically what happens is that the server socket is closed abruptly sending us any Connection*Error exception.
            We can simulate the ConnectionResetError on the client side by sending TCP RST flag when closing the socket.
            But not the ConnectionAbortedError, since it is caused by other reasons (local TCP stack and has nothing
            to do with the remote server).
        """
        # At this stage there could be several times that the same socket was used to the service server - we need to
        # close this socket as well if it still opened.
        # The first part of the condition is to check if the service socket was connected at all.
        # If the service socket couldn't connect, then the instance will be None.
        if service_socket_instance and service_socket_instance.fileno() != -1:
            if origin_service_client_instance.socket_instance:
                origin_service_client_instance.close_socket()

        # If client socket is still opened - close
        if client_socket.fileno() != -1:
            if send_connection_reset:
                # Abort the connection
                linger = struct.pack('ii', 1, 0)
                client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger)
            client_socket.close()

            if send_connection_reset:
                network_logger.info(f"Closed client socket [{client_ip}:{source_port}] with TCP RST flag (Sent ConnectionResetError)...")
            else:
                network_logger.info(f"Closed client socket [{client_ip}:{source_port}]...")

        network_logger.info("Thread Finished. Will continue listening on the Main thread")

    def create_requester_request(
            client_message: ClientMessage,
            sending_socket: socket.socket
    ) -> tuple[bytes, bool]:
        request_received_raw: bytes = client_message.request_raw_bytes
        request_custom_raw: bytes = requester.create_request(client_message, sending_socket=sending_socket)

        if request_custom_raw is None or request_received_raw == request_custom_raw:
            is_requester_worked: bool = False
        else:
            is_requester_worked: bool = True

            # Output first 100 characters of the request.
            requester.logger.info(f"{request_custom_raw[0: 100]}...")

        return request_custom_raw, is_requester_worked

    def create_responder_response(client_message: ClientMessage) -> list[bytes]:
        if client_message.action == 'service_connect':
            return responder.create_connect_response(client_message)
        else:
            # If we're in offline mode, and it's the first cycle and the protocol is Websocket, then we'll create the HTTP Handshake
            # response automatically.
            if config_static.MainConfig.is_offline and protocol == 'Websocket' and client_receive_count == 1:
                responses: list = list()
                responses.append(
                    websocket.create_byte_http_response(client_message.request_raw_bytes))
                responder.logger.info(f"Generated automatic WebSocket response in Offline Mode.")
            else:
                # Creating response for parsed message and printing
                responder_responses: list = responder.create_response(client_message)
                if responder_responses is None:
                    responses: list = [client_message.response_raw_bytes]
                else:
                    responses: list = responder_responses
                    responder.logger.info(f"Generated {len(responses)} responses from responder.")

            # Output first 100 characters of all the responses in the list.
            for response_raw_bytes_single in responses:
                responder.logger.info(f"{response_raw_bytes_single[0: 100]}...")

            return responses

    def create_client_socket(client_message: ClientMessage):
        # Per-subdomain mTLS client cert (None when not configured).
        custom_client_pem_certificate_path: str | None = socket_client.lookup_mtls_client_pem(
            found_domain_module.mtls, client_message.server_name)

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
                    config_static.Certificates.enable_sslkeylogfile_env_to_client_ssl_context),
                sslkeylog_file_path=config_static.Certificates.sslkeylog_file_path,
                client_alpn_offers=client_alpn_offers,
            )
        # If it's a domain name, then we'll use the DNS to resolve it.
        else:
            # If we're on localhost, then use external services list in order to resolve the domain:
            # config['tcp']['forwarding_dns_service_ipv4_list___only_for_localhost']
            if client_message.client_ip in socket_base.THIS_DEVICE_IP_LIST:
                service_client_instance = socket_client.SocketClient(
                    service_name=client_message.server_name,
                    service_port=client_message.destination_port,
                    tls=is_tls,
                    dns_servers_list=[config_static.DNSServer.forwarding_dns_service_ipv4],
                    logger=network_logger,
                    custom_pem_client_certificate_file_path=custom_client_pem_certificate_path,
                    enable_sslkeylogfile_env_to_client_ssl_context=(
                        config_static.Certificates.enable_sslkeylogfile_env_to_client_ssl_context),
                    sslkeylog_file_path=config_static.Certificates.sslkeylog_file_path,
                    client_alpn_offers=client_alpn_offers,
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
                        config_static.Certificates.enable_sslkeylogfile_env_to_client_ssl_context),
                    sslkeylog_file_path=config_static.Certificates.sslkeylog_file_path,
                    client_alpn_offers=client_alpn_offers,
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

        client_message.request_auto_parsed = parse_http(
            client_message.request_raw_bytes, client_message, side='Client')
        # This is needed for each cycle that is not HTTP, but its protocol maybe set by HTTP, like websocket.
        if protocol != '':
            client_message.protocol = protocol

        # FIFO the request method to the response framer for HEAD body elision.
        # Framer install is handled by the Receiver's ProtocolSniffer before this point.
        if client_message.request_auto_parsed is not None and protocol == 'HTTP':
            method = getattr(client_message.request_auto_parsed, 'command', None)
            _push_request_method_fifo(method)

        # # Parse websocket frames only if it is not the first protocol upgrade request.
        # if protocol == 'Websocket' and client_receive_count != 1:
        #     client_message.request_auto_parsed = parse_websocket(client_message.request_raw_bytes)

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

        client_message.response_auto_parsed = parse_http(
            client_message.response_raw_bytes, client_message, side='Service')
        if protocol != '':
            client_message.protocol = protocol

        # Detect WebSocket upgrade response (101 Switching Protocols + Upgrade: websocket)
        # and swap framers on BOTH sides simultaneously. The 101 response is the
        # framing fence: bytes after it on either socket are WebSocket frames.
        parsed = client_message.response_auto_parsed
        status = getattr(parsed, 'code', None) if parsed is not None else None
        if status == 101:
            headers = getattr(parsed, 'headers', None)
            upgrade = ''
            if headers is not None:
                try:
                    upgrade = (headers.get('Upgrade') or '').lower()
                except Exception:
                    upgrade = ''
            if upgrade == 'websocket':
                client_recv = side_receivers.get('Client')
                service_recv = side_receivers.get('Service')
                if client_recv is not None:
                    client_recv.set_framer(WebSocketFramer(direction='client_to_server'))
                if service_recv is not None:
                    service_recv.set_framer(WebSocketFramer(direction='server_to_client'))
                network_logger.info("Framers swapped to WebSocket on 101 Switching Protocols.")

    def client_message_first_start() -> ClientMessage:
        client_message: ClientMessage = ClientMessage()
        client_message.client_name = client_name
        client_message.client_ip = client_ip
        client_message.server_ip = server_ip
        client_message.source_port = source_port
        client_message.destination_port = destination_port
        client_message.server_name = server_name
        client_message.thread_id = thread_id
        client_message.thread_process = thread_process_name
        client_message.process_name = process_commandline
        client_message.engine_name = engine_name

        return client_message

    def receive_send_service_connect(
            client_connection_message: ClientMessage,
            sending_socket: ssl.SSLSocket | socket.socket
    ) -> Literal['continue', 'return'] | None:


        client_message = client_connection_message

        bytes_to_send_list: list[bytes] = create_responder_response(client_message)
        print_api(f"Got responses from connect responder, count: [{len(bytes_to_send_list)}]",
                  logger=network_logger, logger_method='info')

        # If the client message is the connection message, then we'll skip to the next iteration.
        if not bytes_to_send_list:
            return 'continue'

        # is_socket_closed: bool = False
        error_on_send: str = str()
        for bytes_to_send_single in bytes_to_send_list:
            client_message.reinitialize_dynamic_vars()
            client_message.timestamp = datetime.now()
            client_message.response_raw_bytes = bytes_to_send_single
            client_message.action = 'service_responder'
            record_and_statistics_write(client_message)

            # Send the bytes back to the client socket.
            error_on_send: str = sender.Sender(
                ssl_socket=sending_socket, bytes_to_send=bytes_to_send_single,
                logger=network_logger).send()

            if error_on_send:
                client_message.reinitialize_dynamic_vars()
                client_message.errors.append(error_on_send)
                client_message.timestamp = datetime.now()
                client_message.action = 'client_send'
                record_and_statistics_write(client_message)

        if error_on_send:
            exception_or_close_in_receiving_thread.set()
            finish_thread()
            return 'return'

        return None

    def receive_send_client_offline(
            client_message: ClientMessage,
            receiving_socket: ssl.SSLSocket | socket.socket,
            sending_socket: ssl.SSLSocket | socket.socket,
            side_receiver: receiver.Receiver
    ) -> Literal['return'] | None:
        nonlocal client_receive_count

        client_receive_count += 1

        # The Receiver is created once in receive_send_start and reused across
        # all receive cycles for this direction — see Receiver class docstring.
        network_logger.info(f"Receiving Client cycle: {str(client_receive_count)}")
        # receive() returns raw bytes (b'' is a clean EOF) or raises stdlib
        # socket/TLS exceptions tagged with partial bytes as 'received'.
        try:
            received_raw_data: bytes = side_receiver.receive()
            error_cause: BaseException | None = None
        except (ConnectionError, ssl.SSLError, TimeoutError, InterruptedError) as exc:
            received_raw_data = getattr(exc, 'received', b'')
            error_cause = exc
        # is_socket_closed acts as the stop signal for the receive loop —
        # set on clean EOF (b'') or any receive error.
        is_socket_closed: bool = (received_raw_data == b'') or (error_cause is not None)
        error_message: str | None = (
            f"{type(error_cause).__name__}: {error_cause}" if error_cause else None)
        client_message.timestamp = datetime.now()

        process_client_raw_data(received_raw_data, error_message, client_message)
        client_message.action = 'client_receive'
        record_and_statistics_write(client_message)
        if error_message:
            print_api(error_message, logger=network_logger, logger_method='critical')

        # If there was an exception in the service thread, then receiving empty bytes doesn't mean that
        # the socket was closed by the other side, it means that the service thread closed the socket.
        if (received_raw_data == b'' or error_message) and exception_or_close_in_receiving_thread.is_set():
            print_api("Both sockets are closed, breaking the loop", logger=network_logger,
                      logger_method='info')
            return 'return'

        # If the socket was closed on receive, and we're in offline mode, then we'll finish the thread right away.
        # Since nothing more can be done, like responding to service or using requester.
        if is_socket_closed:
            exception_or_close_in_receiving_thread.set()
            finish_thread()
            return 'return'

        # Send to requester.
        # THERE IS ALWAYS WILL BE ONLY ONE REQUEST FROM REQUESTER, SINCE THIS IS WHAT WE GOT FROM THE CLIENT.
        request_custom_raw, is_requester_worked = create_requester_request(client_message, sending_socket=sending_socket)
        # We will not process the raw data if requester didn't change anything.
        if is_requester_worked:
            client_message.reinitialize_dynamic_vars()
            client_message.timestamp = datetime.now()
            client_message.request_raw_bytes = request_custom_raw
            client_message.action = 'client_requester'
            process_client_raw_data(request_custom_raw, error_message, client_message)
            record_and_statistics_write(client_message)

        print_api("Offline Mode, sending to responder directly.", logger=network_logger,
                  logger_method='info')
        bytes_to_send_list: list[bytes] = create_responder_response(client_message)

        error_on_send: str = str()
        for bytes_to_send_single in bytes_to_send_list:
            client_message.reinitialize_dynamic_vars()
            client_message.timestamp = datetime.now()
            client_message.response_raw_bytes = bytes_to_send_single
            client_message.action = 'client_responder_offline'
            process_server_raw_data(bytes_to_send_single, '', client_message)
            record_and_statistics_write(client_message)

            error_on_send: str = sender.Sender(
                ssl_socket=receiving_socket, bytes_to_send=bytes_to_send_single,
                logger=network_logger).send()

            if error_on_send:
                client_message.reinitialize_dynamic_vars()
                client_message.errors.append(error_on_send)
                client_message.timestamp = datetime.now()
                client_message.action = 'service_send'

                record_and_statistics_write(client_message)

        # If the socket was closed on message receive, then we'll break the loop only after send.
        if is_socket_closed or error_on_send:
            exception_or_close_in_receiving_thread.set()
            finish_thread()
            return 'return'

        return None

    def receive_send_client(
            client_message: ClientMessage,
            receiving_socket: ssl.SSLSocket | socket.socket,
            sending_socket: ssl.SSLSocket | socket.socket,
            side_receiver: receiver.Receiver
    ) -> Literal['return'] | None:

        nonlocal client_receive_count

        client_receive_count += 1

        # Reusing the Receiver created in receive_send_start (one per direction,
        # for the connection's lifetime).
        network_logger.info(f"Receiving Client cycle: {str(client_receive_count)}")

        # Getting message from the client over the socket using specific class.
        # receive() returns raw bytes (b'' is a clean EOF) or raises stdlib
        # socket/TLS exceptions tagged with partial bytes as 'received'.
        try:
            received_raw_data: bytes = side_receiver.receive()
            error_cause: BaseException | None = None
        except (ConnectionError, ssl.SSLError, TimeoutError, InterruptedError) as exc:
            received_raw_data = getattr(exc, 'received', b'')
            error_cause = exc
        is_socket_closed: bool = (received_raw_data == b'') or (error_cause is not None)
        error_on_receive: str | None = (
            f"{type(error_cause).__name__}: {error_cause}" if error_cause else None)
        client_message.timestamp = datetime.now()

        process_client_raw_data(received_raw_data, error_on_receive, client_message)
        client_message.action = 'client_receive'

        # If there was an exception in the service thread, then receiving empty bytes doesn't mean that
        # the socket was closed by the other side, it means that the service thread closed the socket.
        if (received_raw_data == b'' or error_on_receive) and exception_or_close_in_receiving_thread.is_set():
            print_api("Both sockets are closed, breaking the loop", logger=network_logger,
                      logger_method='info')
            return 'return'

        # We don't need to record aborted socket receives if the socket was closed on receive on the second socket.
        # Meaning 'exception_or_close_in_receiving_thread.is_set()'.
        record_and_statistics_write(client_message)
        if error_on_receive:
            print_api(error_on_receive, logger=network_logger, logger_method='critical')

        # At this point if the socket was closed on receive, then there's no point to send anything to the service.
        # But if the data was received and then the socket was closed, we first send the data and then close the socket.
        error_on_send: str = str()
        if received_raw_data != b'' and received_raw_data is not None:
            # Send to requester.
            # THERE IS ALWAYS WILL BE ONLY ONE REQUEST FROM REQUESTER, SINCE THIS IS WHAT WE GOT FROM THE CLIENT.
            request_custom_raw, is_requester_worked = create_requester_request(client_message, sending_socket=sending_socket)
            # We will not process the raw data if requester didn't change anything.
            if is_requester_worked:
                client_message.reinitialize_dynamic_vars()
                client_message.timestamp = datetime.now()
                client_message.request_raw_bytes = request_custom_raw
                client_message.action = 'client_requester'
                process_client_raw_data(request_custom_raw, error_on_receive, client_message)
                record_and_statistics_write(client_message)

            error_on_send: str = sender.Sender(
                ssl_socket=sending_socket, bytes_to_send=client_message.request_raw_bytes,
                logger=network_logger).send()

            if error_on_send:
                client_message.reinitialize_dynamic_vars()
                client_message.errors.append(error_on_send)
                client_message.timestamp = datetime.now()
                client_message.action = 'service_send'
                record_and_statistics_write(client_message)

        # If the socket was closed on message receive, then we'll break the loop only after send.
        if is_socket_closed or error_on_send:
            exception_or_close_in_receiving_thread.set()
            finish_thread()
            return 'return'

        return None

    def receive_send_service(
            client_message: ClientMessage,
            receiving_socket: ssl.SSLSocket | socket.socket,
            sending_socket: ssl.SSLSocket | socket.socket,
            side_receiver: receiver.Receiver
    ) -> Literal['return'] | None:

        nonlocal server_receive_count

        server_receive_count += 1

        # Reusing the Receiver created in receive_send_start (one per direction,
        # for the connection's lifetime).
        network_logger.info(f"Receiving Service cycle: {str(server_receive_count)}")

        # Getting message from the client over the socket using specific class.
        # receive() returns raw bytes (b'' is a clean EOF) or raises stdlib
        # socket/TLS exceptions tagged with partial bytes as 'received'.
        try:
            received_raw_data: bytes = side_receiver.receive()
            error_cause: BaseException | None = None
        except (ConnectionError, ssl.SSLError, TimeoutError, InterruptedError) as exc:
            received_raw_data = getattr(exc, 'received', b'')
            error_cause = exc
        is_socket_closed: bool = (received_raw_data == b'') or (error_cause is not None)
        error_on_receive: str | None = (
            f"{type(error_cause).__name__}: {error_cause}" if error_cause else None)
        client_message.timestamp = datetime.now()

        process_server_raw_data(received_raw_data, error_on_receive, client_message)
        client_message.action = 'service_receive'

        # If there was an exception in the service thread, then receiving empty bytes doesn't mean that
        # the socket was closed by the other side, it means that the service thread closed the socket.
        if (received_raw_data == b'' or error_on_receive) and exception_or_close_in_receiving_thread.is_set():
            print_api("Both sockets are closed, breaking the loop", logger=network_logger,
                      logger_method='info')
            return 'return'

        # We don't need to record aborted socket receives if the socket was closed on receive on the second socket.
        # Meaning 'exception_or_close_in_receiving_thread.is_set()'.
        record_and_statistics_write(client_message)
        if error_on_receive:
            print_api(error_on_receive, logger=network_logger, logger_method='critical')

        # At this stage, we have received the response from the service, but there was an exception/error or the socket was simply closed.
        # Meaning the 'received_raw_data' is None for exception or b'' for just closed socket.
        # So, there's no point to send anything back to the client.
        # Close both sockets and finish the threads.
        # But if the data was received and then the socket was closed, we first send the data and then close the socket.
        error_on_send: str = str()
        if received_raw_data != b'' and received_raw_data is not None:
            # Now send it to requester/responder.
            bytes_to_send_list: list[bytes] = create_responder_response(client_message)

            # is_socket_closed: bool = False
            for bytes_to_send_single in bytes_to_send_list:
                client_message.reinitialize_dynamic_vars()
                client_message.timestamp = datetime.now()
                client_message.response_raw_bytes = bytes_to_send_single

                # This records the requester or responder output, only if it is not the same as the original
                # message.
                if bytes_to_send_single != received_raw_data:
                    client_message.action = 'service_responder'
                    record_and_statistics_write(client_message)

                error_on_send: str = sender.Sender(
                    ssl_socket=sending_socket, bytes_to_send=bytes_to_send_single,
                    logger=network_logger).send()

                if error_on_send:
                    client_message.reinitialize_dynamic_vars()
                    client_message.errors.append(error_on_send)
                    client_message.timestamp = datetime.now()
                    client_message.action = 'client_send'

                    record_and_statistics_write(client_message)

        # If the socket was closed on message receive, then we'll break the loop only after send.
        if is_socket_closed or error_on_send:
            exception_or_close_in_receiving_thread.set()

            # Forward TCP reset-style receive failures to the peer on close.
            if isinstance(error_cause, (ConnectionResetError, ConnectionAbortedError)):
                finish_thread(send_connection_reset=True)
            else:
                finish_thread()

            return 'return'

        return None


    def _read_alpn(sock) -> str | None:
        if not hasattr(sock, 'selected_alpn_protocol'):
            return None
        try:
            return sock.selected_alpn_protocol()
        except Exception:
            return None


    def init_framer_for_side(
            receiving_socket,
            side: str,
    ) -> tuple[Framer | None, ProtocolSniffer | None]:
        """Pick the initial framer (and parsers) for one direction from ALPN; sniffer if unknown."""
        nonlocal h2_request_parser, h2_response_parser
        nonlocal mqtt_state, mqtt_request_parser, mqtt_response_parser

        is_client = (side == 'Client')
        alpn = _read_alpn(receiving_socket)
        direction = 'client_to_server' if is_client else 'server_to_client'

        if alpn == 'h2':
            framer: Framer | None = Http2Framer(direction=direction)
            # h2 framer chunks at END_STREAM; autoparser owns H2Connection + HPACK.
            if is_client:
                h2_request_parser = Http2DirectionParser(is_request_side=True)
            else:
                h2_response_parser = Http2DirectionParser(is_request_side=False)
        elif alpn == 'http/1.1':
            framer = Http11Framer(direction=direction)
        elif alpn == 'mqtt':
            framer = MqttFramer(direction=direction)
            # Shared state so c2s CONNECT version applies to s2c CONNACK.
            if mqtt_state is None:
                mqtt_state = MqttConnectionState()
            if is_client:
                mqtt_request_parser = MqttDirectionParser(is_request_side=True, state=mqtt_state)
            else:
                mqtt_response_parser = MqttDirectionParser(is_request_side=False, state=mqtt_state)
        else:
            framer = None  # time-based mode

        # No ALPN → per-direction sniffer; shared state short-circuits s2c after c2s detection.
        sniffer = None
        if framer is None:
            sniffer = ProtocolSniffer(direction=direction, shared=shared_protocol_state)

        framer_name = type(framer).__name__ if framer is not None else 'sniffer'
        network_logger.info(f"Initial framer for {side}: {framer_name} (ALPN={alpn!r})")
        return framer, sniffer


    def receive_send_start(
            receiving_socket,
            sending_socket = None,
            exception_queue: queue.Queue = None,
            client_connection_message: ClientMessage = None
    ):
        nonlocal client_receive_count
        nonlocal server_receive_count
        nonlocal h2_request_parser
        nonlocal h2_response_parser
        nonlocal mqtt_state
        nonlocal mqtt_request_parser
        nonlocal mqtt_response_parser

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

            side_framer, side_protocol_detector = init_framer_for_side(receiving_socket, side)

            # ---- One Receiver per direction, for the connection's lifetime ----
            # Built once here, before the reception loop, instead of allocating a
            # fresh Receiver every cycle. Creating one per cycle had three problems:
            #   1. ``loggingw.get_logger_with_level`` scans the global logger
            #      registry under a lock — calling it on every cycle caused lock
            #      contention with the other direction's logger setup.
            #   2. ``getpeername()`` was called twice on every receive() just to
            #      log a "waiting for data" line; a long-lived Receiver captures
            #      the peer address once at __init__.
            #   3. Creating and discarding an object every cycle added unnecessary
            #      garbage collector work.
            # See the Receiver class docstring for the lifetime contract.
            side_receiver: receiver.Receiver = receiver.Receiver(
                ssl_socket=receiving_socket, logger=network_logger, framer=side_framer,
                protocol_detector=side_protocol_detector)
            # Surface this side's receiver so the other side's flow can swap framers
            # (WebSocket upgrade) and FIFO request methods (HTTP/1.1 HEAD elision).
            side_receivers[side] = side_receiver

            while True:
                client_message.reinitialize_dynamic_vars()

                if side == 'Service' and client_connection_message:
                    result: Literal['continue', 'return'] | None = (
                        receive_send_service_connect(client_connection_message, sending_socket))
                    client_connection_message = None
                    if result == 'continue':
                        continue
                elif side == 'Client' and config_static.MainConfig.is_offline:
                    result: Literal['return'] | None = receive_send_client_offline(
                        client_message, receiving_socket, sending_socket, side_receiver)
                elif side == 'Client':
                    result: Literal['return'] | None = receive_send_client(
                        client_message, receiving_socket, sending_socket, side_receiver)
                elif side == 'Service':
                    result: Literal['return'] | None = receive_send_service(
                        client_message, receiving_socket, sending_socket, side_receiver)
                else:
                    raise ValueError(f"Unknown side [{side}] of the socket: {receiving_socket}")

                if result == 'return':
                    return
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

        exception_or_close_in_receiving_thread.set()
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

        # Add custom attribute to the exception.
        exc.engine_name = client_message.engine_name

        # After the socket clean up, we will still raise the exception to the main thread.
        raise exc

    # ================================================================================================================
    # This is the start of the thread_worker_main function
    network_logger = loggingw.get_logger_with_level(config_static.MainConfig.LOGGER_NAME)

    # Only protocols that are encrypted with TLS have the server name attribute.
    if is_tls:
        # Get current destination domain
        server_name = client_socket.server_hostname
        # If there is no server name from the TLS handshake, then we'll use the domain from the DNS.
        if not server_name:
            server_name = domain_from_dns
    # If the protocol is not TLS, then we'll use the domain from the DNS.
    else:
        server_name = domain_from_dns

    thread_id = threads.current_thread_id()

    process_name: str = multiprocessing.current_process().name
    current_thread = threading.current_thread()
    thread_process_name: str = f"{process_name} | {current_thread.name}"
    current_thread.name = thread_process_name

    # This is the main protocols.
    protocol: str = str()
    # This is the secondary protocol in the websocket.
    protocol3: str = str()
    # # This is Client Masked Frame Parser.
    # websocket_masked_frame_parser = websocket.WebsocketFrameParser()
    # # This is Server UnMasked Frame Parser.
    # websocket_unmasked_frame_parser = websocket.WebsocketFrameParser()
    websocket_frame_parser = websocket.WebsocketFrameParser()

    # Both directions' Receivers, indexed by side. Populated in receive_send_start.
    # Shared across the two parallel threads so process_server_raw_data can swap
    # framers symmetrically on a 101 Switching Protocols response, and so the
    # client thread can FIFO request methods to the service thread's response framer.
    side_receivers: dict = {'Client': None, 'Service': None}

    # Connection-scoped protocol identification shared between the c2s and s2c
    # sniffers. First leg to identify sets it; the other leg short-circuits
    # detection and installs the matching framer immediately.
    shared_protocol_state: SharedProtocolState = SharedProtocolState()

    # HTTP/2 autoparsers, one per direction. Initialised in receive_send_start
    # when ALPN selects 'h2'. HPACK state is connection-scoped, so each lives
    # for the lifetime of the leg; framers stay raw-byte chunkers and feed
    # bytes into these via parse_http's HTTP/2 short-circuit.
    h2_request_parser: Http2DirectionParser | None = None
    h2_response_parser: Http2DirectionParser | None = None

    # MQTT autoparsers, one per direction with a shared MqttConnectionState so
    # the protocol version seen on the c2s CONNECT applies to the s2c CONNACK
    # and beyond. Initialised when ALPN selects 'mqtt'.
    mqtt_state: MqttConnectionState | None = None
    mqtt_request_parser: MqttDirectionParser | None = None
    mqtt_response_parser: MqttDirectionParser | None = None

    # Loading parser by domain, if there is no parser for current domain - general reference parser is loaded.
    # These should be outside any loop and initialized only once entering the thread.
    found_domain_module = initialize_engines.assign_class_by_domain(
        engines_list=engines_list,
        message_domain_name=server_name,
        reference_module=config_static.REFERENCE_MODULE
    )
    parser = found_domain_module.parser_class_object
    requester = found_domain_module.requester_class_object()
    responder = found_domain_module.responder_class_object()
    recorder = found_domain_module.recorder_class_object(record_path=config_static.LogRec.recordings_path)

    engine_name: str = recorder.engine_name

    for engine in engines_list:
        if engine.engine_name == engine_name:
            responder.add_args(engine=engine)
            break

    network_logger.info(f"Assigned Modules for [{server_name}]: "
        f"{parser.__name__}, "
        f"{requester.__class__.__name__}, "
        f"{responder.__class__.__name__}, "
        f"{recorder.__class__.__name__}")

    # Initializing the client message object with current thread's data.
    # This is needed only to skip error alerts after 'try'.
    client_message_connection: ClientMessage = ClientMessage()
    # ---- Cross-thread close signal ----
    # Signals that one of the receiving threads (client side or service side)
    # has either hit a connection error or seen the peer close. The other
    # thread checks this on each iteration: if its own ``recv`` returns no
    # data while this is set, "no data" means "the other thread is bringing
    # the connection down" rather than "the peer closed our side cleanly",
    # so it exits without writing a misleading close event to the log.
    #
    # ``threading.Event`` rather than a bare ``bool`` because:
    #   - both threads read and write this signal; a plain bool has no
    #     thread-safety guarantees (the GIL makes simple bool access safe
    #     in practice, but there is no API contract for it);
    #   - ``Event`` has the right semantic: one-shot transition from
    #     unset to set (this signal is never cleared mid-connection);
    #   - using Event makes the cross-thread signaling intent obvious
    #     from the type alone.
    exception_or_close_in_receiving_thread: threading.Event = threading.Event()
    # ---- Queue for HTTP request URI paths ----
    # The parser pushes a request's path here when it parses an HTTP
    # request, and pops it when the matching response is parsed, so
    # the response's path field can be filled in for stats output.
    #
    # Pipelining assumption: this queue assumes **one HTTP/1.1 request
    # in flight per direction at a time**. If a client sends two
    # pipelined requests before the service has responded, two paths
    # will be enqueued and the responses will pop them in arrival
    # order — which is correct as long as the service responds in
    # the same order (HTTP/1.1 requires this). In practice, almost
    # no modern client pipelines, so this works.
    #
    # If pipelining is needed, path tracking can be moved into the
    # framer's per-message metadata (the framer knows where each
    # request begins and can carry the path with the message bytes),
    # removing this assumption.
    http_path_queue: queue.Queue = queue.Queue()

    try:
        client_ip, source_port = client_socket.getpeername()

        client_name: str = socket_base.get_host_name_from_ip_address_with_timeout(client_ip)

        client_name = client_name.lower()
        destination_port: int = client_socket.getsockname()[1]
        destination_port_str: str = str(destination_port)

        new_thread_name: str = f"{current_thread.name}-{destination_port_str}"
        current_thread.name = new_thread_name

        # If the destination port is in the on_port_connect dictionary, then we'll get the port from there.
        if destination_port_str in found_domain_module.on_port_connect:
            on_port_connect_value = found_domain_module.on_port_connect[destination_port_str]
            _, destination_port_str = initialize_engines.get_ipv4_from_engine_on_connect_port(on_port_connect_value)
            destination_port: int = int(destination_port_str)

        if config_static.MainConfig.is_offline:
            # If in offline mode, then we'll get the TCP server's input address.
            server_ip = client_socket.getsockname()[0]
        else:
            # If not in offline mode, we will get the ip from the socket that will connect later to the service.
            server_ip = ""

        network_logger.info(f"Thread Created - Client [{client_ip}:{source_port}] | "
                            f"Destination service: [{server_name}:{destination_port}]")

        origin_service_client_instance = None
        client_receive_count: int = 0
        server_receive_count: int = 0
        client_message_connection = client_message_first_start()

        # If we're not in offline mode, then we'll create the client socket to the service.
        # noinspection PyTypeChecker
        connection_error: str = None
        service_socket_instance = None
        client_message_connection.action = 'service_connect'
        client_message_connection.timestamp = datetime.now()

        if config_static.MainConfig.is_offline:
            client_message_connection.info = 'Offline Mode'
        else:
            origin_service_client_instance = create_client_socket(client_message_connection)
            service_socket_instance, connection_error = origin_service_client_instance.service_connection()

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
                name=f"{process_name} | Thread-{thread_id}-{destination_port_str}-Client",
                daemon=True)
            client_thread.start()

            service_exception_queue: queue.Queue = queue.Queue()
            if not config_static.MainConfig.is_offline:
                service_thread = threading.Thread(
                    target=receive_send_start,
                    args=(service_socket_instance, client_socket, service_exception_queue, client_message_connection),
                    name=f"{process_name} | Thread-{thread_id}-{destination_port_str}-Service",
                    daemon=True)
                service_thread.start()

            client_thread.join()
            # If we're in offline mode, then there is no service thread.
            if not config_static.MainConfig.is_offline:
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

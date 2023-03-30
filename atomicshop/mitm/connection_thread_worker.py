# v1.0.4 - 28.03.2023 17:30
import ssl
from datetime import datetime

from .message import ClientMessage
from .initialize_engines import assign_class_by_domain
from ..sockets.receiver import Receiver
from ..sockets.sender import Sender
from ..sockets.socket_client import SocketClient
from ..http_parse import HTTPRequestParse, HTTPResponseParse
from ..basics.threads import current_thread_id


# Thread function on client connect.
def thread_worker_main(
        function_client_socket_object: ssl.SSLSocket,
        process_commandline: str,
        network,
        statistics,
        engines_list,
        reference_module,
        config):
    def output_statistics_csv_row():
        statistics_dict['host'] = client_message.server_name
        try:
            statistics_dict['path'] = client_message.request_raw_decoded.path
        except Exception:
            pass
        try:
            statistics_dict['status_code'] = \
                ','.join([str(x.code) for x in client_message.response_list_of_raw_decoded])
        except Exception:
            pass
        try:
            statistics_dict['command'] = client_message.request_raw_decoded.command
        except Exception:
            pass
        try:
            statistics_dict['request_time_sent'] = client_message.request_time_received
        except Exception:
            pass
        try:
            statistics_dict['request_size_bytes'] = len(client_message.request_raw_bytes)
        except Exception:
            pass
        try:
            statistics_dict['response_size_bytes'] = \
                ','.join([str(len(x)) for x in client_message.response_list_of_raw_bytes])
        except Exception:
            pass
        # try:
        #     statistics_dict['request_hex'] = client_message.request_raw_hex
        # except Exception:
        #     pass
        # try:
        #     statistics_dict['response_hex'] = \
        #         f'"' + ','.join([x for x in client_message.response_list_of_raw_hex]) + '"'
        # except Exception:
        #     pass
        try:
            statistics_dict['file_path'] = recorded_file
        except Exception:
            pass
        try:
            statistics_dict['process_cmd'] = process_commandline
        except Exception:
            pass
        statistics_dict['error'] = str()

        statistics.logger.info(f"{statistics_dict['request_time_sent']},"
                               f"{statistics_dict['host']},"
                               f"\"{statistics_dict['path']}\","
                               f"{statistics_dict['command']},"
                               f"{statistics_dict['status_code']},"
                               f"{statistics_dict['request_size_bytes']},"
                               f"{statistics_dict['response_size_bytes']},"
                               # f"{statistics_dict['request_hex']},"
                               # f"{statistics_dict['response_hex']},"
                               f"\"{statistics_dict['file_path']}\","
                               f"\"{statistics_dict['process_cmd']}\","
                               f"{statistics_dict['error']},"
                               )

    # Defining variables before assignment
    function_recorded: bool = False
    client_message: ClientMessage = ClientMessage()
    request_decoded = None
    service_client = None

    # Getting thread ID of the current thread and putting to the client message class
    client_message.thread_id = current_thread_id()
    # Get client ip and port
    client_message.client_ip, client_message.source_port = function_client_socket_object.getpeername()
    # Get destination port
    client_message.destination_port = function_client_socket_object.getsockname()[1]
    # Get current destination domain
    client_message.server_name = function_client_socket_object.server_hostname
    # Putting the process command line.
    client_message.process_name = process_commandline

    network.logger.info(f"Thread Created - Client [{client_message.client_ip}:{client_message.source_port}] | "
                        f"Destination service: [{client_message.server_name}:{client_message.destination_port}]")

    # Loading parser by domain, if there is no parser for current domain - general reference parser is loaded.
    # These should be outside any loop and initialized only once entering the thread.
    parser, responder, recorder = assign_class_by_domain(engines_list,
                                                         client_message.server_name,
                                                         reference_module=reference_module,
                                                         logger=network.logger)

    # Defining client connection boolean variable to enter the loop
    client_connection_boolean: bool = True

    # Loop while received message is not empty, if so, close socket, since other side already closed.
    while client_connection_boolean:
        # Don't forget that 'ClientMessage' object is being reused at this step.
        # Meaning, that each list / dictionary that is used to update at this loop section needs to be reinitialized.
        # Add any variables that need reinitializing in the 'ClientMessage' class 'reinitialize' function.
        client_message.reinitialize()

        # Initialize statistics_dict for the same reason as 'client_message.reinitialize()'.
        statistics_dict: dict = dict()
        statistics_dict['host'] = client_message.server_name
        statistics_dict['path'] = str()
        statistics_dict['status_code'] = str()
        statistics_dict['command'] = str()
        statistics_dict['request_time_sent'] = str()
        statistics_dict['request_size_bytes'] = str()
        # statistics_dict['response_time_sent'] = str()
        statistics_dict['response_size_bytes'] = str()
        statistics_dict['file_path'] = str()
        statistics_dict['process_cmd'] = str()
        statistics_dict['error'] = str()

        network.logger.info("Initializing Receiver")
        # Getting message from the client over the socket using specific class.
        client_received_raw_data = Receiver(function_client_socket_object).receive()

        # If the message is empty, then the connection was closed already by the other side, so we can close the socket
        # as well.
        # If the received message from the client is not empty, then continue.
        if client_received_raw_data:
            # Putting the received message to the aggregating message class.
            client_message.request_raw_bytes = client_received_raw_data
            # Getting current time of message received from client.
            client_message.request_time_received = datetime.now()

            # HTTP Parsing section =====================================================================================
            # Parsing the raw bytes as HTTP.
            try:
                request_decoded = HTTPRequestParse(client_message.request_raw_bytes)
            except Exception:
                network.logger.critical_exception_oneliner("There was an exception in HTTP Parsing module!")
                # Socket connection can be closed since we have a problem in current thread and break the loop
                client_connection_boolean = False
                break

            # Getting the status of http parsing
            request_is_http, http_parsing_reason, http_parsing_error = request_decoded.check_if_http()

            # Currently, we don't care if it's HTTP or not. If there was no error we can continue. Just log the reason.
            if not http_parsing_error:
                network.logger.info(http_parsing_reason)
            # If there was error, it means that the request is really HTTP, but there's a problem with its structure.
            # So, we'll stop the loop.
            else:
                client_message.error = http_parsing_reason
                network.logger.critical(client_message.error)
                break

            # If the request is HTTP protocol.
            if request_is_http:
                network.logger.info(f"Method: {request_decoded.command}")
                network.logger.info(f"Path: {request_decoded.path}")
                # statistics.dict['path'] = request_decoded.path
                client_message.request_raw_decoded = request_decoded
            # HTTP Parsing section EOF =================================================================================

            # Catching exceptions in the parser
            try:
                parser(client_message).parse()
            except Exception:
                message = "Exception in Parser"
                parser.logger.critical_exception_oneliner(message)
                network.logger.critical_exception_oneliner(message)
                # At this point we can pass the exception and continue the script.
                pass
                # Socket connection can be closed since we have a problem in current thread and break the loop
                client_connection_boolean = False
                break

            # Converting body parsed to string, since there is no strict rule for the parameter to be string.
            # Still going to put exception on it, since it is not critical for the server.
            # Won't even log the exception.
            try:
                parser.logger.info(f"{str(client_message.request_body_parsed)[0: 100]}...")
            except Exception:
                pass

            # If we're in response mode, execute responder.
            if config['tcp']['server_response_mode']:
                # Since we're in response mode, we'll record the request anyway, after the responder did its job.
                client_message.info = "In Server Response Mode"

                # Re-initiate the 'client_message.response_list_of_raw_bytes' list, since we'll be appending
                # new entries for empty list.
                client_message.response_list_of_raw_bytes = list()
                # Creating response for parsed message and printing
                try:
                    responder.create_response(client_message)
                except Exception:
                    message = "Exception in Responder"
                    responder.logger.critical_exception_oneliner(message)
                    network.logger.critical_exception_oneliner(message)
                    pass
                    # Socket connection can be closed since we have a problem in current thread and break the loop.
                    client_connection_boolean = False
                    break

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
                    if client_message.client_ip == "127.0.0.1":
                        service_client = SocketClient(
                            service_name=client_message.server_name, service_port=client_message.destination_port,
                            dns_servers_list=config['tcp']['forwarding_dns_service_ipv4_list___only_for_localhost'])
                    # If we're not on localhost, then connect to domain directly.
                    else:
                        service_client = SocketClient(service_name=client_message.server_name,
                                                      service_port=client_message.destination_port)

                # Sending current client message and receiving a response.
                # If there was an error it will be passed to "client_message" object class and if not, "None" will
                # be passed.
                # If there was connection error or socket close, then "ssl_socket" of the "service_client"
                # will be empty.
                response_raw_bytes, client_message.error, client_message.server_ip, service_ssl_socket =\
                    service_client.send_receive_to_service(client_message.request_raw_bytes)

                # Since we need a list for raw bytes, we'll add the 'response_raw_bytes' to our list object.
                # But we need to re-initiate it first.
                client_message.response_list_of_raw_bytes = list()
                client_message.response_list_of_raw_bytes.append(response_raw_bytes)

                client_message.response_list_of_raw_decoded = list()
                # Make HTTP Response parsing only if there was response at all.
                if response_raw_bytes:
                    response_raw_decoded = HTTPResponseParse(response_raw_bytes).response_raw_decoded
                    client_message.response_list_of_raw_decoded.append(response_raw_decoded)

                # So if the socket was closed and there was an error we can break the loop
                if not service_ssl_socket:
                    break

            # This is the point after the response mode check was finished.
            # Recording the message, doesn't matter what type of mode this is.
            try:
                recorded_file = recorder(class_client_message=client_message,
                                         record_path=config['recorder']['recordings_path']).record()
            except Exception:
                message = "Exception in Recorder"
                recorder.logger.critical_exception_oneliner(message)
                network.logger.critical_exception_oneliner(message)
                pass

            function_recorded = True

            # Save statistics file.
            output_statistics_csv_row()

            try:
                # If there is a response, then send it.
                if response_raw_bytes:
                    # Sending response/s to client no matter if in record mode or not.
                    network.logger.info(f"Sending messages to client: {len(client_message.response_list_of_raw_bytes)}")
                    function_data_sent = None

                    # Iterate through the list of byte responses.
                    for response_raw_bytes in client_message.response_list_of_raw_bytes:
                        function_data_sent = Sender(function_client_socket_object, response_raw_bytes).send()

                        # If there was problem with sending data, we'll break current loop.
                        if not function_data_sent:
                            break
                # If there is no response, close the socket.
                else:
                    function_data_sent = None
                    network.logger.info(f"Response empty, nothing to send to client.")
            except Exception:
                network.logger.critical_exception_oneliner(
                    "Not sending anything to the client, since there is no response available")
                # Pass the exception
                pass
                # Break the while loop
                break

            # If there was problem with sending data, we'll break the while loop
            if not function_data_sent:
                break
        else:
            # Ending the while loop, basically we can use 'break'
            client_connection_boolean = False
            # We don't need to record empty message so setting the recorder state to recorded
            function_recorded = True

    # === At this point while loop of 'client_connection_boolean' was broken ===========================================
    # If recorder wasn't executed before, then execute it now
    if not function_recorded:
        try:
            recorded_file = recorder(class_client_message=client_message,
                                     record_path=config['recorder']['recordings_path']).record()
        except Exception:
            message = "Exception in Recorder"
            recorder.logger.critical_exception_oneliner(message)
            network.logger.critical_exception_oneliner(message)
            pass

        # Save statistics file.
        output_statistics_csv_row()

    # At this stage there could be several times that the same socket was used to the service server - we need to
    # close this socket as well if it still opened.
    if service_client:
        if service_client.ssl_socket:
            service_client.close_socket()

    # If client socket is still opened - close
    if function_client_socket_object:
        function_client_socket_object.close()
        network.logger.info(f"Closed client socket [{client_message.client_ip}:{client_message.source_port}]...")

    network.logger.info("Thread Finished. Will continue listening on the Main thread")

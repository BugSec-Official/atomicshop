# These are specified with hardcoded paths instead of relative, because 'create_module_template.py' copies the content.
from atomicshop.mitm.engines.__parent.responder___parent import ResponderParent
from atomicshop.mitm.shared_functions import create_custom_logger
from atomicshop.mitm.message import ClientMessage
from atomicshop.mitm import config_static
from atomicshop.wrappers.protocol_parsers import websocket
from atomicshop.wrappers.protocol_parsers import http2
from atomicshop.wrappers.protocol_parsers import mqtt

"""
import time
datetime
import binascii

# This is 'example' '.proto' file that contains message 'ExampleResponse'.
from .example_pb2 import ExampleRequest
# Import from 'protobuf' the 'json_format' library.
from google.protobuf import json_format
"""


class ResponderGeneral(ResponderParent):
    """The class that is responsible for generating response to client based on the received message."""
    # When initializing main classes through "super" you need to pass parameters to init
    def __init__(self):
        super().__init__()

        self.logger = create_custom_logger()

    # def create_response(self, class_client_message: ClientMessage):
    #     # noinspection GrazieInspection
    #     """
    #     Function to create Response based on ClientMessage and its Request.
    #
    #     :param class_client_message: contains request and other parameters to help creating response.
    #     :return: list of responses in bytes.
    #     -----------------------------------
    #
    #     # Example of creating list of bytes using 'build_byte_response' function:
    #     # Auto-filled by build_byte_response:
    #     #   http_version    <- class_client_message.request_auto_parsed.request_version
    #     #   Reason phrase   <- HTTPStatus(status_code).phrase
    #     #   Content-Length  <- len(body), only when absent from headers
    #     result_list: list[bytes] = list()
    #     result_list.append(
    #         self.build_byte_response(
    #             class_client_message,
    #             status_code=200,
    #             headers=response_headers,
    #             body=b'',
    #         )
    #     )
    #
    #     return result_list
    #     -----------------------------------
    #     # Example of extracting variables from URL PATH based on custom PATH TEMPLATE:
    #     # (more examples in 'self.extract_variables_from_path_template' function description)
    #     template_path: str = "/hithere/<variable1>/else/<variable2>/tested/"
    #     path_variables: dict = extract_variables_from_path_template(
    #         path=class_client_message.request_raw_decoded.path,
    #         template_path=template_path
    #     )
    #     -----------------------------------
    #     # Example of extracting value from URL PATH parameters after question mark:
    #     parameter_value = extract_value_from_path_parameter(
    #         path=class_client_message.request_raw_decoded.path,
    #         parameter='test_id'
    #     )
    #     """
    #
    #     # byte_response: bytes = b''
    #     # self.logger.info(f"Response: {byte_response}")
    #
    #     response_bytes_list: list[bytes] = list()
    #     # response_bytes_list.append(byte_response)
    #     return response_bytes_list

    # def create_connect_response(self, class_client_message: ClientMessage):
    #     """
    #     This is almost the same as 'create_response' function, but it's used only when the client connects and before
    #     sending any data.
    #     """
    #
    #     # byte_response: bytes = b''
    #     # self.logger.info(f"Response: {byte_response}")
    #
    #     response_bytes_list: list[bytes] = list()
    #     # response_bytes_list.append(byte_response)
    #     return response_bytes_list
    #
    # ==================================================================================================================
    #
    # WEBSOCKET example.
    # def create_response(self, class_client_message: ClientMessage):
    #     # The incoming websocket frame is parsed into a dict with keys:
    #     #   'is_deflated' (bool), 'is_masked' (bool), 'frame' (str or bytes),
    #     #   'opcode' (str: TEXT/BINARY/CLOSE/PING/PONG)
    #     ws_frame = class_client_message.request_auto_parsed
    #     frame_data = ws_frame['frame']
    #     frame_opcode = ws_frame['opcode']
    #
    #     response_bytes_list: list[bytes] = list()
    #
    #     # Auto-filled by build_byte_websocket_frame:
    #     #   mask=False (RFC 6455 §5.1 — server-side frames are never masked)
    #     #   opcode    <- inferred from data type (str -> TEXT, bytes -> BINARY)
    #     #   deflate   <- self._ws_state.permessage_deflate_negotiated (from 101 handshake)
    #     # import json
    #     if frame_opcode == 'TEXT':
    #         # request_dict = json.loads(frame_data)
    #         response_dict = {'status': 'ok', 'echo': frame_data}
    #         response_bytes_list.append(self.build_byte_websocket_frame(
    #             class_client_message, data=json.dumps(response_dict)))
    #     elif frame_opcode == 'BINARY':
    #         response_bytes_list.append(self.build_byte_websocket_frame(
    #             class_client_message, data=b'\x01\x02\x03'))
    #
    #     # Close frame example.
    #     # Auto-filled by build_byte_websocket_close:
    #     #   mask=False, opcode=CLOSE, payload = 2-byte big-endian code + reason.encode()
    #     # response_bytes_list.append(self.build_byte_websocket_close(
    #     #     class_client_message, code=1000, reason='normal closure'))
    #
    #     return response_bytes_list
    #
    # ==================================================================================================================
    # HTTP/2 response synthesis example.
    # def create_response(self, class_client_message: ClientMessage):
    #     ar = class_client_message.request_auto_parsed
    #     # Only handle HTTP/2 here; pass-through otherwise.
    #     if not isinstance(ar, http2.Http2RequestParse):
    #         return None
    #
    #     response_bytes_list: list[bytes] = list()
    #
    #     # 1. JSON response: synthesise a 200 OK on the same stream the client opened.
    #     # Auto-filled by build_byte_http2_response:
    #     #   stream_id            <- class_client_message.request_auto_parsed.stream_id
    #     #   DATA fragmentation   <- self._h2_state.max_frame_size (from client SETTINGS)
    #     #   content-length       <- len(body), only when absent from headers
    #     # (HPACK encoding stays per-call with sensitive=True; not connection-scoped.)
    #     # import json
    #     # body: bytes = json.dumps({'ok': True, 'echo_path': ar.path}).encode()
    #     body: bytes = b'{"ok": true}'
    #     headers = {'content-type': 'application/json'}
    #     response_bytes_list.append(self.build_byte_http2_response(
    #         class_client_message, status_code=200, headers=headers, body=body))
    #
    #     # 2. Empty-body response (e.g. 204 No Content): same auto-fills.
    #     # response_bytes_list.append(self.build_byte_http2_response(
    #     #     class_client_message, status_code=204, headers={}, body=b''))
    #
    #     # 3. gRPC-style response with trailers (HEADERS-DATA-HEADERS): same auto-fills.
    #     # response_bytes_list.append(self.build_byte_http2_response(
    #     #     class_client_message,
    #     #     status_code=200,
    #     #     headers={'content-type': 'application/grpc'},
    #     #     body=b'\x00\x00\x00\x00\x05hello',
    #     #     trailers={'grpc-status': '0', 'grpc-message': 'OK'}))
    #
    #     # 4. Route by method + path (mirrors the HTTP/1.1 example):
    #     # if ar.command == 'POST' and ar.path.startswith('/api/v1/echo'):
    #     #     body = ar.body or b'<empty>'
    #     #     response_bytes_list.append(self.build_byte_http2_response(
    #     #         class_client_message, status_code=200,
    #     #         headers={'content-type': 'application/octet-stream'}, body=body))
    #
    #     return response_bytes_list
    #
    # ==================================================================================================================
    # MQTT response synthesis example (broker-side).
    # The incoming MqttPacketParse exposes: .packet_type ('CONNECT'/'PUBLISH'/...),
    # .qos / .retain / .dup, .topic, .payload, .packet_identifier, .client_id,
    # .subscriptions ([(filter, requested_qos), ...]), .protocol_version (4=v3.1.1, 5=v5).
    # def create_response(self, class_client_message: ClientMessage):
    #     mp = class_client_message.request_auto_parsed
    #     if not isinstance(mp, mqtt.MqttPacketParse):
    #         return None
    #
    #     response_bytes_list: list[bytes] = list()
    #
    #     # CONNACK — accept the session.
    #     # Auto-filled by build_byte_mqtt_connack:
    #     #   protocol_version  <- self._mqtt_state.protocol_version (set from c2s CONNECT)
    #     if mp.packet_type == 'CONNECT':
    #         response_bytes_list.append(self.build_byte_mqtt_connack(
    #             class_client_message, session_present=False, return_code=0))
    #
    #     # SUBACK — grant each topic at the requested QoS.
    #     # Auto-filled by build_byte_mqtt_suback:
    #     #   packet_identifier <- class_client_message.request_auto_parsed.packet_identifier
    #     #   protocol_version  <- self._mqtt_state.protocol_version
    #     elif mp.packet_type == 'SUBSCRIBE':
    #         granted = [requested_qos for _topic, requested_qos in (mp.subscriptions or [])]
    #         response_bytes_list.append(self.build_byte_mqtt_suback(
    #             class_client_message, return_codes=granted))
    #
    #     # PUBACK / PUBREC for inbound PUBLISH at QoS>0; broker-initiated downstream PUBLISH.
    #     elif mp.packet_type == 'PUBLISH':
    #         # Auto-filled by build_byte_mqtt_puback / build_byte_mqtt_pubrec:
    #         #   packet_identifier <- class_client_message.request_auto_parsed.packet_identifier
    #         #   protocol_version  <- self._mqtt_state.protocol_version
    #         if mp.qos == 1:
    #             response_bytes_list.append(self.build_byte_mqtt_puback(class_client_message))
    #         elif mp.qos == 2:
    #             response_bytes_list.append(self.build_byte_mqtt_pubrec(class_client_message))
    #
    #         # Broker-initiated downstream PUBLISH (e.g. echo to subscribers).
    #         # Auto-filled by build_byte_mqtt_publish:
    #         #   protocol_version   <- self._mqtt_state.protocol_version
    #         # Engine-supplied:
    #         #   packet_identifier  <- required for qos>0 (omit at qos=0)
    #         response_bytes_list.append(self.build_byte_mqtt_publish(
    #             class_client_message, topic=mp.topic, payload=mp.payload or b'',
    #             qos=0, retain=False))
    #         # If echoing at qos>0, pass packet_identifier explicitly:
    #         # response_bytes_list.append(self.build_byte_mqtt_publish(
    #         #     class_client_message, topic=mp.topic, payload=mp.payload or b'',
    #         #     qos=1, retain=False, packet_identifier=12345))
    #
    #     # PUBCOMP — completes a QoS 2 handshake after the client's PUBREL.
    #     # Auto-filled: packet_identifier, protocol_version (same as puback).
    #     elif mp.packet_type == 'PUBREL':
    #         response_bytes_list.append(self.build_byte_mqtt_pubcomp(class_client_message))
    #
    #     # PINGRESP — fixed 2 bytes (0xD0 0x00); no session state used.
    #     elif mp.packet_type == 'PINGREQ':
    #         response_bytes_list.append(self.build_byte_mqtt_pingresp(class_client_message))
    #
    #     # UNSUBACK after UNSUBSCRIBE.
    #     # Auto-filled: packet_identifier, protocol_version. v5 carries return_codes; v3 ignores.
    #     elif mp.packet_type == 'UNSUBSCRIBE':
    #         filters = mp.topic_filters or []
    #         response_bytes_list.append(self.build_byte_mqtt_unsuback(
    #             class_client_message, return_codes=[0] * len(filters)))
    #
    #     # Tear-down: broker-initiated DISCONNECT (v5 carries reason_code).
    #     # Auto-filled: protocol_version.
    #     # response_bytes_list.append(self.build_byte_mqtt_disconnect(
    #     #     class_client_message, reason_code=0x8E))  # 0x8E = Session taken over (v5)
    #
    #     return response_bytes_list
    #
    # ==================================================================================================================
    # Uncomment this section in order to begin building custom responder.
    # @staticmethod
    # def get_current_formatted_time_http():
    #     # Example: 'Tue, 08 Nov 2022 14:23: 00 GMT'
    #     return time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
    #
    # def get_current_formatted_time_protobuf():
    #     # Example: '2023-02-08T13:49:50.247686031Z'
    #     return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f000Z")
    #
    # def response_dir_example(self, req_parsed_body):
    #     # === Protobuf helper functions =========================
    #     # Copy to current protobuf object from another protobuf object.
    #     # Example: you want to copy content of key 'example' inside 'ExampleRequest' message to the key 'example' of
    #     # 'ExampleResponse'.
    #     example_response.example.CopyFrom(example_request.example)
    #
    #     # Get 'datetime' python object from protobuf time object. Example: 'ExampleRequest' message and its
    #     # time key 'timeTest'.
    #     python_datetime = example_request.time_test.ToDatetime()
    #
    #
    #     # === Building body. ===========================
    #     # Remove a key from request body.
    #     _ = req_parsed_body.pop('some_key', None)
    #
    #     # Set 'timeTest' to time 'now()' in protobuf format. There's pure protobuf implementation below.
    #     req_parsed_body['time_test'] = self.get_current_formatted_time_protobuf()
    #
    #     # Create an empty message.
    #     example_response = example_pb2.ExampleResponse()
    #     # Get the json string of your dict.
    #     json_string = json.dumps(req_parsed_body)
    #
    #     # Put the json contents into the empty message and return filled message.
    #     resp_body_protobuf = json_format.Parse(json_string, example_response)
    #
    #     # Setting 'timeTest' key to 'now'.
    #     resp_body_protobuf.time_test.FromDatetime(datetime.datetime.now())
    #
    #     # Convert protobuf message to bytes.
    #     resp_body = resp_body_protobuf.SerializeToString()
    #
    #     # === Building Status Code. ===========================
    #     resp_status_code = 200
    #
    #     # === Building Headers. ===========================
    #     # Response Date example: 'Tue, 08 Nov 2022 14:23: 00 GMT'
    #     resp_headers = {
    #         'Date': self.get_current_formatted_time_http(),
    #         'Content-Type': 'application/x-protobuf',
    #         'Content-Length': str(len(resp_body)),
    #     }
    #
    #     return resp_status_code, resp_headers, resp_body
    #
    # def response_dir_test(self, req_body, test):
    #     # === Building body. ===========================
    #     resp_body = test.encode()
    #
    #     # === Building Status Code. ===========================
    #     resp_status_code = 200
    #
    #     # === Building Headers. ===========================
    #     # Response Date example: 'Tue, 08 Nov 2022 14:23: 00 GMT'
    #     resp_headers = {
    #         'Date': self.get_current_formatted_time_http(),
    #         'Content-Length': str(len(resp_body)),
    #     }
    #
    #     return resp_status_code, resp_headers, resp_body
    #
    # def response_dir_something(self, test):
    #     # === Building body. ===========================
    #     # 11 AB CD
    #     constant_bytes = binascii.unhexlify('11ABCD')
    #
    #     # Adding to constant response bytes.
    #     resp_body = constant_bytes + test.encode()
    #
    #     # === Building Status Code. ===========================
    #     resp_status_code = 200
    #
    #     # === Building Headers. ===========================
    #     # Response Date example: 'Tue, 08 Nov 2022 14:23: 00 GMT'
    #     resp_headers = {
    #         'Date': self.get_current_formatted_time_http(),
    #         'Content-Length': str(len(resp_body)),
    #         'Connection': 'keep-alive'
    #     }
    #
    #     return resp_status_code, resp_headers, resp_body
    #
    # def create_response(self, class_client_message: ClientMessage):
    #     # Arranging important request entries to appropriate variables.
    #     req_path = class_client_message.request_auto_parsed.path
    #     req_command = class_client_message.request_auto_parsed.command
    #     req_headers = class_client_message.request_auto_parsed.headers
    #     req_body = class_client_message.request_auto_parsed.body
    #
    #     # ====================================
    #     # Case specific.
    #     request_header_content_type = req_headers['Content-Type']
    #
    #     # URI cases.
    #     if req_path == '/dir/example/' and req_command == 'POST':
    #         resp_status_code, resp_headers, resp_body_bytes = self.response_dir_example(
    #             req_body=req_body, test=request_header_content_type)
    #     elif req_path == '/dir/test/' and req_command == 'POST':
    #         resp_status_code, resp_headers, resp_body_bytes = self.response_dir_test(
    #             test=request_header_content_type)
    #     elif req_path == '/dir/something/' and req_command == 'POST':
    #         resp_status_code, resp_headers, resp_body_bytes = self.response_dir_something(
    #             req_parsed_body=class_client_message.request_body_parsed)
    #     else:
    #         resp_status_code = None
    #         resp_headers = None
    #         resp_body_bytes = None
    #
    #     # ==============================================================================
    #     # === Building byte response. ==================================================
    #     # Auto-filled by build_byte_response:
    #     #   http_version    <- class_client_message.request_auto_parsed.request_version
    #     #   Reason phrase   <- HTTPStatus(status_code).phrase
    #     #   Content-Length  <- len(body), only when absent from headers
    #     byte_response = self.build_byte_response(
    #         class_client_message,
    #         status_code=resp_status_code,
    #         headers=resp_headers,
    #         body=resp_body_bytes,
    #     )
    #
    #     result_response_list: list[bytes] = [byte_response]
    #     return result_response_list
    #
    # ==================================================================================================================
    # TEST RESPONSE.
    # def create_response(self, class_client_message: ClientMessage):
    #     resp_body: bytes = b"<html><body>TEST OK!</body></html>\n"
    #     resp_headers: dict = {"Content-Type": "text/html; charset=utf-8"}
    #
    #     # Auto-filled by build_byte_response:
    #     #   http_version    <- class_client_message.request_auto_parsed.request_version
    #     #   Reason phrase   <- HTTPStatus(status_code).phrase
    #     #   Content-Length  <- len(body), only when absent from headers
    #     byte_response = self.build_byte_response(
    #         class_client_message,
    #         status_code=200,
    #         headers=resp_headers,
    #         body=resp_body,
    #     )
    #     return [byte_response]
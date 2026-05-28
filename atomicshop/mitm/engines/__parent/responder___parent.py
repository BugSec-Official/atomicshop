# Using to convert status code to status phrase / string.
from http import HTTPStatus
# Parsing PATH template to variables.
from pathlib import PurePosixPath
from urllib.parse import unquote
# Needed to extract parameters after question mark in URL / Path.
from urllib.parse import urlparse
from urllib.parse import parse_qs

from ...message import ClientMessage
from ....wrappers.protocol_parsers.http import HTTPResponseParse
from ....wrappers.protocol_parsers import http2
from ....wrappers.protocol_parsers import mqtt
from ....wrappers.protocol_parsers import websocket
from ....wrappers.protocol_parsers.http2 import Http2ConnectionState
from ....wrappers.protocol_parsers.mqtt import MqttConnectionState
from ....wrappers.protocol_parsers.websocket import WebSocketConnectionState
from ....print_api import print_api

from atomicshop.mitm.shared_functions import create_custom_logger


class ResponderParent:
    """The class that is responsible for generating response to client based on the received message."""
    def __init__(self):
        self.logger = create_custom_logger()
        # engine: initialize_engines.ModuleCategory
        self.engine = None
        # Connection-scoped state for build_byte_* helpers; wired via add_args.
        self._h2_state: Http2ConnectionState | None = None
        self._mqtt_state: MqttConnectionState | None = None
        self._ws_state: WebSocketConnectionState | None = None

    def add_args(
            self,
            # engine: initialize_engines.ModuleCategory
            engine = None,
            h2_state: Http2ConnectionState | None = None,
            mqtt_state: MqttConnectionState | None = None,
            ws_state: WebSocketConnectionState | None = None,
    ):
        """Backward-compatible state injection. Adds connection-scoped state for build_byte_* helpers."""
        self.engine = engine
        self._h2_state = h2_state
        self._mqtt_state = mqtt_state
        self._ws_state = ws_state

    @staticmethod
    def get_path_parts(path: str):
        """
        Gets PATH as string and extracts all its directories to list

        Example: url = 'http://www.example.com/hithere/something/else'
        PurePosixPath(unquote(urlparse(url).path)).parts[1]
        returns 'hithere' (the same for the URL with parameters)
        parts holds ('/', 'hithere', 'something', 'else')
                      0    1          2            3
        Another fact, if path ends with "/" it doesn't matter, since it doesn't count as one more directory

        :param path: path from URL.
        :return: tuple of path parts.
        """
        return PurePosixPath(unquote(path)).parts

    def extract_variables_from_path_template(self, path: str, template_path: str):
        """
        Extracting variables from PATH based on PATH TEMPLATE.
        Example 1:
            path = "/hithere/something/else/"
            template_path = "/hithere/<variable1>/else/"
            dictionary_result = {'variable1': 'something'}
        Example 2:
            path = "/hithere/something/else/stuff/tested/"
            template_path = "/hithere/<variable1>/else/<variable2>/tested/"
            dictionary_result = {'variable1': 'something', 'variable2': 'stuff'}
        Example 3:
            path = "/hithere/something/else/tested/"
            template_path = "/hithere/<variable1>/else/<variable2>/tested/"
            dictionary_result = {}
            Console output: Different number of parts between PATH and TEMPLATE.

        :param path: URI path.
        :param template_path: template URI path that contains variable to extract. A variable you want to extract will
            be wrapped between triangle brackets ("<>").
        :return: dict object with extracted variables.
        """

        # Defining locals.
        dictionary_result: dict = dict()

        # Getting the parts of PATH and the TEMPLATE.
        path_parts: tuple = self.get_path_parts(path)
        template_parts: tuple = self.get_path_parts(template_path)

        if len(path_parts) != len(template_parts):
            self.logger.error("Different number of parts between PATH and TEMPLATE.")
        else:
            for index, value in enumerate(template_parts):
                if template_parts[index] != path_parts[index]:
                    current_template_part = template_parts[index].replace('<', '').replace('>', '')
                    dictionary_result[current_template_part] = path_parts[index]

        return dictionary_result

    def extract_value_from_path_parameter(self, path: str, parameter: str):
        """
        Function ot extract parameter's value within URL / Path after question mark.

        :param path: URL / URL Path in string.
        :param parameter: the needed parameter in string that you want to extract from URL / Path after question mark.
        :return: extracted value of the parameter.
        """

        # "urllib.parse.urlparse" works with URL, but it doesn't matter since it works with strings, and we provide
        # it a URI path.
        # "urlparse(self.path)" is parsing the URL / Path.
        # ".query" property of "urlparse" returns only the string after the "query" / question mark.
        # "parse_qs()" returns a list of all the parameters after the question mark.
        # "['test_id']" is a specific parameter from the URL that we need to return the value for
        # The value returned to the first "[0]" parameter of the list, the second is "len()"
        # Reference from Flask: test_id = request.args.get('test_id')
        # Example for value of 'test_id' parameter: parameter_value = parse_qs(urlparse(path).query)['test_id'][0]
        try:
            parameter_value = parse_qs(urlparse(path).query)[parameter][0]
        except Exception as exception_object:
            self.logger.error_exception_oneliner(exception_object)
            parameter_value = str()
            pass

        return parameter_value

    def build_byte_response(
            self,
            class_client_message: ClientMessage,
            status_code: int,
            headers: dict | None = None,
            body: bytes = b'',
            http_version: str | None = None,
    ) -> bytes:
        """Build HTTP/1.x response wire bytes.

        Auto-filled from class_client_message:
          - http_version    <- request_auto_parsed.request_version
          - Reason phrase   <- HTTPStatus(status_code).phrase
          - Content-Length  <- len(body), only when absent from headers and body is non-empty

        :param class_client_message: supplies request_version from request_auto_parsed.
        :param status_code: HTTP status code (reason phrase derived from HTTPStatus).
        :param headers: response headers; Content-Length auto-added when absent.
        :param body: response body bytes.
        :param http_version: BACKWARDS-COMPAT NO-OP. The wire version is always read
            from class_client_message.request_auto_parsed.request_version. Any value
            passed here is silently discarded. Kept in the signature so existing
            engines passing `http_version=...` as a kwarg don't break with TypeError;
            new code should omit it.
        :return: HTTP/1.x response bytes.
        """
        _ = http_version  # discarded; auto-filled from request below
        http_version_to_use = class_client_message.request_auto_parsed.request_version
        headers = dict(headers or {})
        # Auto-fill Content-Length when absent and body is non-empty so the response
        # is wire-valid without engine-side bookkeeping.
        has_length_header = any(k.lower() == 'content-length' for k in headers)
        if body and not has_length_header:
            headers['Content-Length'] = str(len(body))

        status_full = f"{http_version_to_use} {status_code} {HTTPStatus(status_code).phrase}\r\n"
        headers_string = ''.join(f"{k}: {v}\r\n" for k, v in headers.items())
        return (status_full + headers_string + "\r\n").encode() + body

    def build_byte_http2_response(
            self,
            class_client_message: ClientMessage,
            status_code: int,
            headers: dict | None = None,
            body: bytes = b'',
            trailers: dict | None = None,
    ) -> bytes:
        """Build HTTP/2 response wire bytes on the request's stream.

        Auto-filled from class_client_message + self._h2_state:
          - stream_id        <- request_auto_parsed.stream_id
          - DATA framing     <- self._h2_state.max_frame_size (client SETTINGS)
          - content-length   <- len(body) when absent from headers

        HPACK encoding uses sensitive=True per http2._encode_header_block docstring;
        the dynamic table is intentionally NOT shared across calls — this prevents
        synthesised responses from polluting the client's HPACK decoder state on
        proxies that mix synthesised and forwarded traffic.

        :raises ValueError: stream_id missing/zero on the request, or header block
            exceeds the client's MAX_HEADER_LIST_SIZE SETTING.
        :raises RuntimeError: Http2ConnectionState not wired (add_args missing h2_state).
        """
        if self._h2_state is None:
            raise RuntimeError(
                "build_byte_http2_response: Http2ConnectionState not wired; "
                "check add_args call in the framework")

        ar = class_client_message.request_auto_parsed
        stream_id = getattr(ar, 'stream_id', None)
        if not stream_id:
            raise ValueError(
                f"build_byte_http2_response: request_auto_parsed.stream_id required (got {stream_id!r})")

        headers = dict(headers or {})
        has_length_header = any(k.lower() == 'content-length' for k in headers)
        if body and not has_length_header:
            headers['content-length'] = str(len(body))

        # MAX_HEADER_LIST_SIZE enforcement per RFC 7541 §4.1 (name + value + 32 bytes).
        all_headers = [(':status', str(status_code))] + list(headers.items())
        header_size = sum(len(k) + len(v) + 32 for k, v in all_headers)
        limit = self._h2_state.max_header_list_size
        if limit is not None and header_size > limit:
            raise ValueError(
                f"build_byte_http2_response: header list size {header_size} exceeds "
                f"client SETTINGS_MAX_HEADER_LIST_SIZE {limit}")

        return http2.encode_http2_response(
            status_code=status_code,
            headers=headers,
            body=body,
            stream_id=stream_id,
            trailers=trailers,
            max_frame_size=self._h2_state.max_frame_size,
        )

    # ------------------------------------------------------------------
    # MQTT broker-side response builders. All auto-fill protocol_version
    # from self._mqtt_state; acknowledgements also auto-fill
    # packet_identifier from class_client_message.request_auto_parsed.
    # ------------------------------------------------------------------

    def _require_mqtt_state(self, helper_name: str) -> MqttConnectionState:
        if self._mqtt_state is None:
            raise RuntimeError(
                f"{helper_name}: MqttConnectionState not wired; check add_args call in framework")
        return self._mqtt_state

    def _require_mqtt_packet_id(self, class_client_message: ClientMessage, helper_name: str) -> int:
        pid = getattr(class_client_message.request_auto_parsed, 'packet_identifier', None)
        if pid is None:
            raise ValueError(f"{helper_name}: request_auto_parsed.packet_identifier required")
        return pid

    def build_byte_mqtt_connack(
            self,
            class_client_message: ClientMessage,
            session_present: bool = False,
            return_code: int = 0,
    ) -> bytes:
        """CONNACK accepting the session. Auto-fills protocol_version."""
        st = self._require_mqtt_state('build_byte_mqtt_connack')
        _ = class_client_message  # accepted for API consistency
        return mqtt.encode_connack(
            session_present=session_present,
            return_code=return_code,
            protocol_version=st.protocol_version,
        )

    def build_byte_mqtt_puback(self, class_client_message: ClientMessage) -> bytes:
        """PUBACK for inbound PUBLISH QoS=1. Auto-fills packet_identifier and protocol_version."""
        st = self._require_mqtt_state('build_byte_mqtt_puback')
        pid = self._require_mqtt_packet_id(class_client_message, 'build_byte_mqtt_puback')
        return mqtt.encode_puback(packet_identifier=pid, protocol_version=st.protocol_version)

    def build_byte_mqtt_pubrec(self, class_client_message: ClientMessage) -> bytes:
        """PUBREC for inbound PUBLISH QoS=2 (first of four). Auto-fills pid + version."""
        st = self._require_mqtt_state('build_byte_mqtt_pubrec')
        pid = self._require_mqtt_packet_id(class_client_message, 'build_byte_mqtt_pubrec')
        return mqtt.encode_pubrec(packet_identifier=pid, protocol_version=st.protocol_version)

    def build_byte_mqtt_pubcomp(self, class_client_message: ClientMessage) -> bytes:
        """PUBCOMP completing QoS=2 handshake. Auto-fills pid + version."""
        st = self._require_mqtt_state('build_byte_mqtt_pubcomp')
        pid = self._require_mqtt_packet_id(class_client_message, 'build_byte_mqtt_pubcomp')
        return mqtt.encode_pubcomp(packet_identifier=pid, protocol_version=st.protocol_version)

    def build_byte_mqtt_suback(
            self,
            class_client_message: ClientMessage,
            return_codes: list[int],
    ) -> bytes:
        """SUBACK granting per-topic QoS. Auto-fills pid + version. Engine supplies return_codes."""
        st = self._require_mqtt_state('build_byte_mqtt_suback')
        pid = self._require_mqtt_packet_id(class_client_message, 'build_byte_mqtt_suback')
        return mqtt.encode_suback(
            packet_identifier=pid, return_codes=return_codes, protocol_version=st.protocol_version)

    def build_byte_mqtt_unsuback(
            self,
            class_client_message: ClientMessage,
            return_codes: list[int] | None = None,
    ) -> bytes:
        """UNSUBACK. Auto-fills pid + version. v5 carries return_codes; v3 ignores."""
        st = self._require_mqtt_state('build_byte_mqtt_unsuback')
        pid = self._require_mqtt_packet_id(class_client_message, 'build_byte_mqtt_unsuback')
        return mqtt.encode_unsuback(
            packet_identifier=pid, return_codes=return_codes, protocol_version=st.protocol_version)

    def build_byte_mqtt_pingresp(self, class_client_message: ClientMessage) -> bytes:
        """PINGRESP: fixed 0xD0 0x00, no session state used."""
        _ = class_client_message  # API consistency
        return mqtt.encode_pingresp()

    def build_byte_mqtt_publish(
            self,
            class_client_message: ClientMessage,
            topic: str,
            payload: bytes = b'',
            qos: int = 0,
            retain: bool = False,
            packet_identifier: int | None = None,
    ) -> bytes:
        """Broker-initiated PUBLISH. Auto-fills protocol_version.

        At qos>0, packet_identifier is required (broker chooses one for outbound PUBLISH;
        the framework doesn't track outbound pid counters).
        """
        st = self._require_mqtt_state('build_byte_mqtt_publish')
        _ = class_client_message  # API consistency
        if qos > 0 and packet_identifier is None:
            raise ValueError(
                f"build_byte_mqtt_publish: packet_identifier required when qos>0 (got qos={qos})")
        return mqtt.encode_publish(
            topic=topic, payload=payload, qos=qos, retain=retain,
            protocol_version=st.protocol_version,
            packet_identifier=packet_identifier,
        )

    def build_byte_mqtt_disconnect(
            self,
            class_client_message: ClientMessage,
            reason_code: int = 0,
    ) -> bytes:
        """DISCONNECT (broker-initiated). v5 carries reason_code; v3 ignores."""
        st = self._require_mqtt_state('build_byte_mqtt_disconnect')
        _ = class_client_message
        return mqtt.encode_disconnect(reason_code=reason_code, protocol_version=st.protocol_version)

    # ------------------------------------------------------------------
    # WebSocket server->client frame builders. All auto-fill mask=False
    # (RFC 6455 §5.1) and deflate from self._ws_state.permessage_deflate_negotiated.
    # ------------------------------------------------------------------

    # RFC 6455 §5.2 control-frame opcodes.
    _WS_OPCODE_CLOSE = 0x8
    _WS_OPCODE_PING = 0x9
    _WS_OPCODE_PONG = 0xA

    def _ws_deflate(self) -> bool:
        return bool(self._ws_state and self._ws_state.permessage_deflate_negotiated)

    def build_byte_websocket_frame(
            self,
            class_client_message: ClientMessage,
            data: str | bytes,
    ) -> bytes:
        """Build a WebSocket data frame. Auto-fills mask=False, opcode (from data type),
        deflate (from negotiated extensions).
        """
        _ = class_client_message
        if not isinstance(data, (str, bytes, bytearray)):
            raise TypeError(
                f"build_byte_websocket_frame: data must be str or bytes, got {type(data).__name__}")
        return websocket.create_websocket_frame(data=data, deflate=self._ws_deflate(), mask=False)

    def build_byte_websocket_close(
            self,
            class_client_message: ClientMessage,
            code: int = 1000,
            reason: str = '',
    ) -> bytes:
        """Build a WebSocket CLOSE frame. Payload = 2-byte big-endian code + reason.encode()."""
        _ = class_client_message
        payload = code.to_bytes(2, 'big') + reason.encode()
        return websocket.create_websocket_frame(
            data=payload, deflate=False, mask=False, opcode=self._WS_OPCODE_CLOSE)

    def build_byte_websocket_ping(
            self,
            class_client_message: ClientMessage,
            data: bytes = b'',
    ) -> bytes:
        """Build a WebSocket PING frame."""
        _ = class_client_message
        return websocket.create_websocket_frame(
            data=data, deflate=False, mask=False, opcode=self._WS_OPCODE_PING)

    def build_byte_websocket_pong(
            self,
            class_client_message: ClientMessage,
            data: bytes = b'',
    ) -> bytes:
        """Build a WebSocket PONG frame."""
        _ = class_client_message
        return websocket.create_websocket_frame(
            data=data, deflate=False, mask=False, opcode=self._WS_OPCODE_PONG)

    @staticmethod
    def create_connect_response(class_client_message: ClientMessage):
        """ This function should be overridden in the child class. """

        _ = class_client_message
        response_bytes_list: list[bytes] = list()
        return response_bytes_list

    def create_response(self, class_client_message: ClientMessage):
        """ This function should be overridden in the child class. """

        return None

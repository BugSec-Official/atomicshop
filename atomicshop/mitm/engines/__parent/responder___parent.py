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

    @staticmethod
    def create_connect_response(class_client_message: ClientMessage):
        """ This function should be overridden in the child class. """

        _ = class_client_message
        response_bytes_list: list[bytes] = list()
        return response_bytes_list

    def create_response(self, class_client_message: ClientMessage):
        """ This function should be overridden in the child class. """

        return None

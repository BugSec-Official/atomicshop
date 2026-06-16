# These are specified with hardcoded paths instead of relative, because 'create_module_template.py' copies the content.
from atomicshop.mitm.engines.__parent.parser___parent import ParserParent
from atomicshop.mitm.shared_functions import create_custom_logger
from atomicshop.mitm.message import ClientMessage


"""
# This is 'example' '.proto' file that contains message 'ExampleRequest'.
from .example_pb2 import ExampleRequest
# Import from 'protobuf' library of function 'MessageToDict' that
converts protobuf message object type to python dict.
from google.protobuf.json_format import MessageToDict
"""


# Class that parses the message received from client.
class ParserGeneral(ParserParent):
    # When initializing main classes through "super" you need to pass parameters to init
    def __init__(self, class_client_message: ClientMessage):
        super().__init__(class_client_message)

        self.logger = create_custom_logger()

    # ==================================================================================================================
    # Uncomment this section in order to begin building custom responder.
    # def parse_example_request(self):
    #     # Create empty 'ExampleRequest' message.
    #     example_request = ExampleRequest()
    #     # Using 'ParseFromString' function of the message.
    #     # This returns integer with number of total bytes - the length of the body AND parses the string to object.
    #     total_bytes = example_request.ParseFromString(self.class_client_message.request_raw_decoded.body)
    #
    #     # Convert the parsed body from proto object to dictionary by proto function 'MessageToDict'.
    #     dict_obj = MessageToDict(example_request)
    #
    #     self.class_client_message.request_body_parsed = dict_obj
    #
    # def parse(self):
    #     # Arranging important request entries to appropriate variables.
    #     try:
    #         req_path = self.class_client_message.request_raw_decoded.path
    #     except AttributeError:
    #         req_path = str()
    #
    #     try:
    #         req_command = self.class_client_message.request_raw_decoded.command
    #     except AttributeError:
    #         req_command = str()
    #     # req_headers = self.class_client_message.request_raw_decoded.headers
    #     # req_body = self.class_client_message.request_raw_decoded.body
    #
    #     # If http attributes are not present it means that this is not HTTP request.
    #
    #     # URI cases.
    #     if req_path == '/dir/example' and req_command == 'POST':
    #         self.parse_example_request()
    #     # Rest of the cases insert empty body.
    #     else:
    #         self.class_client_message.request_body_parsed = b''
    #
    #     try:
    #         self.logger.info(f"Parsed: {str(self.class_client_message.request_body_parsed[0: 100])}...")
    #     except Exception as exception_object:
    #         pass

    # ==================================================================================================================
    # HTTP/2 (Http2RequestParse) — fields available on self.class_client_message.request_auto_parsed when ALPN=h2:
    #   .command         -> ':method' uppercased ('GET', 'POST', ...)
    #   .path            -> ':path' (full path + query, e.g. '/api/v1/foo?bar=baz')
    #   .authority       -> ':authority' (Host equivalent)
    #   .scheme          -> ':scheme' ('https' / 'http')
    #   .headers         -> dict[str, str] regular headers (lowercase keys, h2 wire-native)
    #   .pseudo_headers  -> dict[str, str] of all ':...' fields (':method', ':path', ':authority', ':scheme')
    #   .body            -> bytes, joined from DATA frames
    #   .trailers        -> dict[str, str] (e.g. gRPC sets 'grpc-status' here)
    #   .stream_id       -> int; pass to build_byte_http2_response to reply on the same stream
    #
    # def parse(self):
    #     ar = self.class_client_message.request_auto_parsed
    #
    #     # 1. Route by method + path prefix
    #     if ar.command == 'POST' and ar.path.startswith('/api/v1/parse'):
    #         self.parse_example_request()
    #
    #     # 2. Read a regular header — keys are always lowercase in HTTP/2
    #     user_agent: str = ar.headers.get('user-agent', '')
    #
    #     # 3. Read a pseudo-header explicitly (':authority' is the Host equivalent)
    #     authority: str = ar.pseudo_headers.get(':authority', '')
    #
    #     # 4. Stash stream_id so the responder can answer on the same stream
    #     self.class_client_message.request_custom_parsed = {
    #         'method': ar.command, 'path': ar.path,
    #         'stream_id': ar.stream_id, 'body_len': len(ar.body),
    #     }
    #
    #     # 5. gRPC-style trailers (HEADERS frame after DATA frames; usually empty)
    #     grpc_status: str = ar.trailers.get('grpc-status', '')

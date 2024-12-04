# These are specified with hardcoded paths instead of relative, because 'create_module_template.py' copies the content.
from atomicshop.mitm.engines.__parent.responder___parent import ResponderParent
from atomicshop.mitm.shared_functions import create_custom_logger
from atomicshop.mitm.message import ClientMessage

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

    def create_response(self, class_client_message: ClientMessage):
        # noinspection GrazieInspection
        """
        Function to create Response based on ClientMessage and its Request.

        :param class_client_message: contains request and other parameters to help creating response.
        :return: list of responses in bytes.
        -----------------------------------

        # Example of creating list of bytes using 'build_byte_response' function:
        result_list: list[bytes] = list()
        result_list.append(
            self.build_byte_response(
                http_version=class_client_message.request_raw_decoded.request_version,
                status_code=200,
                headers=response_headers,
                body=b''
            )
        )

        return result_list
        -----------------------------------
        # Example of extracting variables from URL PATH based on custom PATH TEMPLATE:
        # (more examples in 'self.extract_variables_from_path_template' function description)
        template_path: str = "/hithere/<variable1>/else/<variable2>/tested/"
        path_variables: dict = extract_variables_from_path_template(
            path=class_client_message.request_raw_decoded.path,
            template_path=template_path
        )
        -----------------------------------
        # Example of extracting value from URL PATH parameters after question mark:
        parameter_value = extract_value_from_path_parameter(
            path=class_client_message.request_raw_decoded.path,
            parameter='test_id'
        )
        """

        # byte_response: bytes = b''
        # self.logger.info(f"Response: {byte_response}")

        response_bytes_list: list[bytes] = list()
        # response_bytes_list.append(byte_response)
        return response_bytes_list

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
    #     byte_response = self.build_byte_response(
    #         http_version=class_client_message.request_auto_parsed.request_version,
    #         status_code=resp_status_code,
    #         headers=resp_headers,
    #         body=resp_body_bytes
    #     )
    #
    #     result_response_list: list[bytes] = [byte_response]
    #     return result_response_list

# These are specified with hardcoded paths instead of relative, because 'create_module_template.py' copies the content.
from atomicshop.mitm.engines.__parent.requester___parent import RequesterParent
from atomicshop.mitm.shared_functions import create_custom_logger
from atomicshop.mitm.message import ClientMessage
from atomicshop.mitm import config_static

"""
import time
datetime
import binascii

# This is 'example' '.proto' file that contains message 'ExampleResponse'.
from .example_pb2 import ExampleRequest
# Import from 'protobuf' the 'json_format' library.
from google.protobuf import json_format
"""


class RequesterGeneral(RequesterParent):
    """The class that is responsible for generating request to client based on the received message."""
    # When initializing main classes through "super" you need to pass parameters to init
    def __init__(self):
        super().__init__()

        self.logger = create_custom_logger()

    # def create_request(self, class_client_message: ClientMessage):
    #     # noinspection GrazieInspection
    #     """
    #     For more examples check the responder.
    #     Function to create Response based on ClientMessage and its Request.
    #
    #     :param class_client_message: contains request and other parameters to help creating response.
    #     :return: 1 request in byte string.
    #     -----------------------------------
    #
    #     # Example of creating byte string using 'build_byte_request' function:
    #     request_bytes: bytes = self.build_byte_request(
    #         http_method=class_client_message.request_raw_decoded.command,
    #         endpoint=class_client_message.request_raw_decoded.path,
    #             http_version=class_client_message.request_raw_decoded.request_version,
    #             headers=response_headers,
    #             body=b''
    #     )
    #
    #     return request_bytes
    #     -----------------------------------

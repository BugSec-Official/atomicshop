# Using to convert status code to status phrase / string.
from http import HTTPStatus
# Parsing PATH template to variables.
from pathlib import PurePosixPath
from urllib.parse import unquote
# Needed to extract parameters after question mark in URL / Path.
from urllib.parse import urlparse
from urllib.parse import parse_qs

from ...message import ClientMessage
from .... import http_parse
from ....print_api import print_api

from atomicshop.mitm.shared_functions import create_custom_logger


class RequesterParent:
    """The class that is responsible for generating request to client based on the received message."""
    def __init__(self):
        self.logger = create_custom_logger()

    def build_byte_request(
            self,
            http_method: str,
            endpoint: str,
            http_version: str,
            headers: dict,
            body: bytes
    ) -> bytes:
        # noinspection GrazieInspection
        """
                Create genuine request from input parameters.
                ---------------
                The request is built from:
                <http_method> <endpoint> <http_version>\r\n
                Headers1: Value\r\n
                Headers2: Value\r\n
                \r\n                        # This is meant to end the headers' section
                Body                        # Request doesn't end with '\r\n\r\n'
                ---------------
                Example for POST request:
                POST /api/v1/resource HTTP/1.1\r\n
                Cache-Control: max-age=86400\r\n
                Content-Type: application/json; charset=utf-8\r\n
                \r\n
                {"id":1,"name":"something"}
                ---------------
                You can create response as:

                ...POST endpoint/api/1 HTTP/1.1
                header1: value
                header2: value

                {data: value}...

                Change 3 dots ("...") to 3 double quotes before "POST" and after "value}".
                This way there will be "\n" added automatically after each line.
                While, the HTTP Client does the parsing of the text and not raw data, most probably it will be parsed well,
                but genuine requests from HTTP sources come with "\r\n" at the end of the line, so better use these for
                better compatibility.
                ---------------

                :param http_method: HTTP Method of Request, e.g. 'GET', 'POST', etc.
                :param endpoint: Endpoint of Request, e.g. '/api/v1/resource'.
                :param http_version: HTTP Version of Response in HTTP Status line.
                :param headers: HTTP Headers of Response.
                :param body: HTTP body data of Response, bytes.
                :return: bytes of the response.
                """

        try:
            # CHeck if the HTTP method is valid.
            if http_method not in http_parse.get_request_methods():
                raise ValueError(f"Invalid HTTP Method: {http_method}")

            # Building the full method endpoint string line and the "\r\n" in the end.
            method_full: str = f"{http_method} {endpoint} {http_version}\r\n"

            # Defining headers string.
            headers_string: str = str()
            # Adding all the headers to the full response
            for keys, values in headers.items():
                headers_string = headers_string + str(keys) + ": " + str(values) + "\r\n"

            # Building full string request.
            # 1. Adding full method line.
            # 2. Adding headers string.
            # 3. Adding a line that end headers (with "\r\n").
            # 4. Adding body as byte string.
            request_full_no_body: str = method_full + headers_string + "\r\n"

            # Converting the HTTP Request string to bytes and adding 'body' bytes.
            request_raw_bytes = request_full_no_body.encode() + body
        except ValueError as exception_object:
            message = \
                f'Create Byte request function error, of the of values provided is not standard: {exception_object}'
            print_api(message, error_type=True, logger=self.logger, logger_method='error', color='red')

            request_raw_bytes = b''

        # Parsing the request we created.
        request_parse_test = http_parse.HTTPRequestParse(request_raw_bytes)
        # If there were errors during parsing, it means that something is wrong with response created.
        if request_parse_test.error_message:
            self.logger.error(request_parse_test.error_message)
            request_raw_bytes = b''
        else:
            self.logger.info("Created Valid Byte Request.")

        return request_raw_bytes

    def create_request(self, class_client_message: ClientMessage):
        """ This function should be overridden in the child class. """

        request_bytes: bytes = class_client_message.request_raw_bytes
        return request_bytes

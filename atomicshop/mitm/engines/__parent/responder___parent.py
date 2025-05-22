# Using to convert status code to status phrase / string.
from http import HTTPStatus
# Parsing PATH template to variables.
from pathlib import PurePosixPath
from urllib.parse import unquote
# Needed to extract parameters after question mark in URL / Path.
from urllib.parse import urlparse
from urllib.parse import parse_qs

from ...message import ClientMessage
from ....http_parse import HTTPResponseParse
from ....print_api import print_api

from atomicshop.mitm.shared_functions import create_custom_logger


class ResponderParent:
    """The class that is responsible for generating response to client based on the received message."""
    def __init__(self):
        self.logger = create_custom_logger()

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
            http_version: str,
            status_code: int,
            headers: dict,
            body: bytes
    ) -> bytes:
        # noinspection GrazieInspection
        """
                Create genuine response from input parameters.
                ---------------
                The response is built from:
                HTTP-Version HTTP-Status HTTP-Status-String\r\n
                Headers1: Value\r\n
                Headers2: Value\r\n
                \r\n                        # This is meant to end the headers' section
                Body\r\n\r\n                # In most cases Body is ended with '\r\n\r\n'
                ---------------
                Example for 200 response:
                HTTP/1.1 200 OK\r\n
                Cache-Control: max-age=86400\r\n
                Content-Type: application/json; charset=utf-8\r\n
                \r\n
                {"id":1,"name":"something"}
                ---------------
                The final response will look like oneline string:
                HTTP/1.1 200 OK\r\nCache-Control: max-age=86400\r\n
                Content-Type: application/json; charset=utf-8\r\n\r\n{"id":1,"name":"something"}
                ---------------
                You can create response as:

                ...HTTP/1.1 200 OK
                header1: value
                header2: value

                {data: value}...

                Change 3 dots ("...") to 3 double quotes before "HTTP" and after "value}".
                This way there will be "\n" added automatically after each line.
                While, the HTTP Client does the parsing of the text and not raw data, most probably it will be parsed well,
                but genuine responses from HTTP sources come with "\r\n" at the end of the line, so better use these for
                better compatibility.
                ---------------

                :param http_version: HTTP Version of Response in HTTP Status line.
                :param status_code: HTTP Status Code of Response in HTTP Status line.
                :param headers: HTTP Headers of Response.
                :param body: HTTP body data of Response, bytes.
                :return: bytes of the response.
                """

        try:
            # Building full status string line and the "\r\n" to the end of the status line
            status_full: str = http_version + " " + str(status_code) + " " + HTTPStatus(status_code).phrase + "\r\n"

            # Defining headers string.
            headers_string: str = str()
            # Adding all the headers to the full response
            for keys, values in headers.items():
                headers_string = headers_string + str(keys) + ": " + str(values) + "\r\n"

            # Building full string response.
            # 1. Adding full status lines.
            # 2. Adding headers string.
            # 3. Adding a line that end headers (with "\r\n").
            # 4. Adding body as byte string.
            response_full_no_body: str = status_full + headers_string + "\r\n"

            # Converting the HTTP Response string to bytes and adding 'body' bytes.
            response_raw_bytes = response_full_no_body.encode() + body
        except ValueError as exception_object:
            message = \
                f'Create Byte response function error, of the of values provided is not standard: {exception_object}'
            print_api(message, error_type=True, logger=self.logger, logger_method='error', color='red')

            response_raw_bytes = b''

        # Parsing the response we created.
        response_parse_test = HTTPResponseParse(response_raw_bytes)
        # If there were errors during parsing, it means that something is wrong with response created.
        if response_parse_test.error:
            self.logger.error(response_parse_test.error)
            response_raw_bytes = b''
        else:
            self.logger.info("Created Valid Byte Response.")

        return response_raw_bytes

    @staticmethod
    def create_connect_response(class_client_message: ClientMessage):
        """ This function should be overridden in the child class. """

        _ = class_client_message
        response_bytes_list: list[bytes] = list()
        return response_bytes_list

    def create_response(self, class_client_message: ClientMessage):
        """ This function should be overridden in the child class. """

        response_bytes_list: list[bytes] = [class_client_message.response_raw_bytes]
        return response_bytes_list

from http.server import BaseHTTPRequestHandler
from http.client import HTTPResponse
import http
from io import BytesIO


def get_request_methods() -> list[str]:
    """
    Function to return all available HTTP request methods.
    """
    # noinspection PyUnresolvedReferences
    return [method.value for method in http.HTTPMethod]


def is_first_bytes_http_request(request_bytes: bytes) -> bool:
    """
    Function to check if the first bytes are HTTP request or not.
    """
    http_request_methods_list: list = get_request_methods()
    http_request_methods_list = [method.encode() for method in http_request_methods_list]

    # If the first bytes are HTTP request, then the first word should be one of the HTTP request methods.
    for method in http_request_methods_list:
        if request_bytes.startswith(method):
            return True
    return False


def is_first_bytes_http_response(response_bytes: bytes) -> bool:
    """
    Function to check if the first bytes are HTTP response or not.
    """
    http_response_beginning: bytes = b'HTTP/'

    # If the first bytes are HTTP response, then the first word should be 'HTTP/'.
    if response_bytes.startswith(http_response_beginning):
        return True
    return False


class HTTPRequestParse(BaseHTTPRequestHandler):
    """
    The class will parse HTTP requests.
    Example implementation:

    # Parsing the raw bytes as HTTP.
            try:
                request_decoded = HTTPRequestParse(client_message.request_raw_bytes)
            except Exception:
                network.logger.critical_exception_oneliner("There was an exception in HTTP Parsing module!")
                # Socket connection can be closed since we have a problem in current thread and break the loop
                client_connection_boolean = False
                break

            # If there's any error in HTTP parsing
            if request_decoded.error_message:
                # If error status is "BAD_REQUEST"
                if request_decoded.error_message.startswith("Bad request"):
                    # If it's 'Bad request syntax' it means that it's not even close to HTTP request, so we can
                    # continue the execution and parse the code as NOT HTTP Request.
                    if "Bad request syntax" in request_decoded.error_message:
                        network.logger.info(f"HTTP Parsing: Not HTTP request: {request_decoded.error_message}")
                    # If it's any other 'Bad Request', it means that it is partially HTTP Request, but there
                    # was some problem parsing it in the middle. If so, it won't get to the destination
                    # Server any way, so we'll log the error and break the current thread.
                    else:
                        client_message.error = f"HTTP Parsing: HTTP Request with ERROR: {request_decoded.error_message}"
                        network.logger.critical(client_message.error)
                        break
                else:
                    client_message.error = \
                        f"HTTP Parsing: HTTP Request with Script Undocumented ERROR: {request_decoded.error_message}"
                    network.logger.critical(client_message.error)
                    break
            # If there's no error at all in HTTP Parsing, then it's fine HTTP Request
            else:
                network.logger.info("HTTP Parsing: HTTP request")

            network.logger.info(f"Method: {request_decoded.command}")
            network.logger.info(f"Path: {request_decoded.path}")

            client_message.request_raw_decoded = request_decoded
    """

    # noinspection PyMissingConstructor
    def __init__(self, request_bytes: bytes):
        self.request_bytes: bytes = request_bytes

        # noinspection PyTypeChecker
        self.rfile = None
        self.raw_requestline = None
        self.error_code = None
        self.error_message = None

        self.content_length = None
        self.body = None
        # noinspection PyTypeChecker
        self.path = None

    # noinspection PyMethodOverriding
    def send_error(self, code, message):
        self.error_code = code
        self.error_message = message

    def parse(self):
        """
        Function to check if parsed object is HTTP request or not.
        'reason' will be populated with parsing status and errors.
        'function_result' will return 'True' / 'False' if it's really HTTP Request or not.
        'error' will be 'True' if the request is HTTP, but there were errors in HTTP itself. If the 'function_result'
            is 'False', then 'error' will be 'False' either, since we're sure it is not HTTP Request.

        Implementation example:
        # Parsing the raw bytes as HTTP.
        try:
            request_decoded = HTTPRequestParse(client_message.request_raw_bytes)
        except Exception:
            print("There was an exception in HTTP Parsing module!")
            raise

        # Getting the status of http parsing
        request_is_http, http_parsing_reason, http_parsing_error = request_decoded.check_if_http()

        # Currently, we don't care if it's HTTP or not. If there was no error we can continue. Just log the reason.
        if not http_parsing_error:
            print(http_parsing_reason)
        # If there was error, it means that the request is really HTTP, but there's a problem with its structure.
        # We can't continue execution.
        else:
            raise(http_parsing_reason)

        # If the request is HTTP protocol.
        if request_is_http:
            print(f"Method: {request_decoded.command}")
            print(f"Path: {request_decoded.path}")

            client_message.request_raw_decoded = request_decoded
        """

        if self.request_bytes is None or not is_first_bytes_http_request(self.request_bytes):
            error = "HTTP Request Parsing: Not HTTP request by first bytes."
            is_http = False
        else:
            error: str = str()

            self.rfile = BytesIO(self.request_bytes)
            self.raw_requestline = self.rfile.readline()
            self.error_code = self.error_message = None
            self.parse_request()

            # Before checking for body, we need to make sure that ".headers" property exists, if not, return empty values.
            if hasattr(self, 'headers'):
                # The "body" of request is in the 'Content-Length' key. If it exists in "headers" - get the body
                if 'Content-Length' in self.headers.keys():
                    # "self.headers.get('Content-Length')" returns number in string format, "int" converts it to integer
                    self.content_length = int(self.headers.get('Content-Length'))
                    self.body = self.rfile.read(self.content_length)

            # Examples:
            # Getting path: self.path
            # Getting Request Version: self.request_version
            # Getting specific header: self.headers['host']

            # If there's any error in HTTP parsing
            if self.error_message:
                # If error status is "BAD_REQUEST"
                if self.error_message.startswith("Bad request"):
                    # If it's 'Bad request' this is not HTTP request, so we can
                    # continue the execution and parse the code as NON-HTTP Request.
                    # Currently, seen 'Bad request syntax' and 'Bad request version'.
                    error = f"HTTP Request Parsing: Not HTTP request: {self.error_message}"
                    is_http = False
                else:
                    error = f"HTTP Request Parsing: HTTP Request with Script Undocumented ERROR: {self.error_message}"
                    is_http = False
            # If there's no error at all in HTTP Parsing, then it's fine HTTP Request
            else:
                is_http = True

        return self, is_http, error


class FakeSocket:
    """
    FakeSocket mimics a socket object for parsing HTTP responses.
    """
    def __init__(self, response_bytes):
        self._file = BytesIO(response_bytes)

    # noinspection PyUnusedLocal
    def makefile(self, mode='rb', buffering=-1) -> BytesIO:
        """
        Mimics the socket's makefile method, returning the BytesIO object.
        """
        return self._file

    def fileno(self) -> int:
        """
        Provide a dummy file descriptor, as some code might call this.
        """
        raise OSError("File descriptor not available in FakeSocket")


class HTTPResponseParse:
    def __init__(self, response_raw_bytes: bytes):
        self.response_raw_bytes: bytes = response_raw_bytes

        self.error = None
        self.source = None
        self.response_raw_parsed = None
        self.is_http: bool = False

    def parse(self):
        if self.response_raw_bytes is None or not is_first_bytes_http_response(self.response_raw_bytes):
            self.error = "HTTP Response Parsing: Not a valid HTTP Response by first bytes."
            self.is_http = False
            self.response_raw_parsed = None
        else:
            # Assigning FakeSocket with response_raw_bytes.
            self.source = FakeSocket(self.response_raw_bytes)

            # Initializing HTTPResponse class with the FakeSocket with response_raw_bytes as input.
            # noinspection PyTypeChecker
            self.response_raw_parsed = HTTPResponse(self.source)

            # Try to parse HTTP Response.
            try:
                self.response_raw_parsed.begin()
                self.is_http = True
            # If there were problems with the status line.
            except http.client.BadStatusLine:
                self.error = "HTTP Response Parsing: Not a valid HTTP Response: Bad Status Line."
                self.is_http = False

            header_exists: bool = False
            if (self.response_raw_parsed is not None and hasattr(self.response_raw_parsed, 'headers') and
                    self.response_raw_parsed.headers is not None):
                header_exists = True

            if header_exists and self.response_raw_parsed.headers.defects:
                self.error = f"HTTP Response Parsing: Not a valid HTTP Response: Some defects in headers: " \
                             f"{self.response_raw_parsed.headers.defects}"
                self.is_http = False

            if self.is_http:
                # Before checking for body, we need to make sure that ".headers" property exists,
                # if not, return empty values.
                self.response_raw_parsed.content_length = None
                self.response_raw_parsed.body = None
                if header_exists and 'Content-Length' in self.response_raw_parsed.headers.keys():
                    # The "body" of response is in the 'Content-Length' key. If it exists in "headers" - get the body.
                    # "self.response_raw_decoded.headers.get('Content-Length')" returns number in string format,
                    # "int" converts it to integer.
                    self.response_raw_parsed.content_length = int(self.response_raw_parsed.headers.get('Content-Length'))
                    # Basically we need to extract only the number of bytes specified in 'Content-Length' from the end
                    # of the response that we received.
                    # self.response_raw_bytes[-23:]
                    self.response_raw_parsed.body = self.response_raw_bytes[-self.response_raw_parsed.content_length:]

        return self.response_raw_parsed, self.is_http, self.error

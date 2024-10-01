from typing import Union
import logging

from websockets.server import ServerProtocol
from websockets.client import ClientProtocol
from websockets.extensions.permessage_deflate import ServerPerMessageDeflateFactory, ClientPerMessageDeflateFactory
from websockets.http11 import Request, Response
from websockets.frames import Frame, Opcode, Close
from websockets.uri import parse_uri
from websockets.exceptions import InvalidHeaderValue
from websockets.protocol import OPEN


class WebsocketRequestParse:
    """
    Parse the websocket request and return the data
    """
    def __init__(
            self,
            enable_logging: bool = False,
    ):
        """
        Initialize the websocket parser.

        :param enable_logging: bool: Enable logging for the websocket protocol.
        """
        # noinspection PyTypeChecker
        self.request_bytes: bytes = None

        # Set up extensions
        permessage_deflate_factory = ServerPerMessageDeflateFactory()

        # Create the protocol instance
        self.protocol = ServerProtocol(
            extensions=[permessage_deflate_factory],
        )
        # At this state the protocol.state is State.CONNECTING

        if enable_logging:
            logging.basicConfig(level=logging.DEBUG)
            self.protocol.logger.setLevel(logging.DEBUG)

    def parse(
            self,
            request_bytes: bytes
    ) -> Union[str, bytes, Request]:
        """
        Parse the websocket request and return the data

        :param request_bytes: bytes: The raw bytes of the websocket request.
        :return: Request: The parsed request object.
        """

        self.protocol.receive_data(request_bytes)
        events = self.protocol.events_received()
        for event in events:
            if isinstance(event, Request):
                # Accept the handshake.
                # After the response is sent, it means the handshake was successful, the protocol.state is State.OPEN
                # Only after this state we can parse frames.
                response = self.protocol.accept(event)
                self.protocol.send_response(response)
                return event
            elif isinstance(event, Frame):
                frame = event
                if frame.opcode == Opcode.TEXT:
                    message = frame.data.decode('utf-8')
                    return message
                elif frame.opcode == Opcode.BINARY:
                    return frame.data

                """
                # Handle control frames, these are here for the future references.
                elif frame.opcode == Opcode.CLOSE:
                    close_info = Close.parse(frame.data)
                    print(f"Connection closed by client: {close_info.code}, {close_info.reason}")
                    # Send a close frame in response if not already sent
                    if self.protocol.state == self.protocol.OPEN:
                        self.protocol.send_close()
                elif frame.opcode == Opcode.PING:
                    # Respond to ping with pong
                    self.protocol.send_pong(frame.data)
                elif frame.opcode == Opcode.PONG:
                    print("Received pong")
                """


class WebsocketResponseParse:
    """
    Parse the websocket response and return the data
    """
    def __init__(
            self,
            enable_logging: bool = False,
    ):
        """
        Initialize the websocket parser.

        :param enable_logging: bool: Enable logging for the websocket protocol.
        """
        # noinspection PyTypeChecker
        self.response_bytes: bytes = None

        # Set up extensions
        permessage_deflate_factory = ClientPerMessageDeflateFactory()

        # Parse the WebSocket URI.
        # Since we're parsing the response, we don't need the URI, but the protocol object requires it.
        # So we will just use a dummy URI.
        wsuri = parse_uri('ws://example.com/websocket')

        # Create the protocol instance
        self.protocol = ClientProtocol(
            wsuri,
            extensions=[permessage_deflate_factory],
        )

        if enable_logging:
            logging.basicConfig(level=logging.DEBUG)
            # self.protocol.logger.setLevel(logging.DEBUG)
            self.protocol.debug = True

        # Perform the handshake and emulate the connection and request sending.
        request = self.protocol.connect()
        self.protocol.send_request(request)
        _ = self.protocol.data_to_send()
        # At this state the protocol.state is State.CONNECTING

    def parse(
            self,
            response_bytes: bytes
    ) -> Union[str, bytes, Response]:
        """
        Parse the websocket response and return the data

        :param response_bytes: bytes: The raw bytes of the websocket response.
        :return: The parsed response.
        """

        self.protocol.receive_data(response_bytes)
        events = self.protocol.events_received()
        for event in events:
            if isinstance(event, Response):
                # Accept the handshake.
                # After the response is sent, it means the handshake was successful, the protocol.state is State.OPEN
                # Only after this state we can parse frames.
                try:
                    self.protocol.process_response(event)
                except InvalidHeaderValue as e:
                    headers = event.headers
                    self.protocol.extensions = self.protocol.process_extensions(headers)
                    self.protocol.subprotocol = self.protocol.process_subprotocol(headers)
                    self.protocol.state = OPEN
                return event
            elif isinstance(event, Frame):
                frame = event
                if frame.opcode == Opcode.TEXT:
                    message = frame.data.decode('utf-8')
                    return message
                elif frame.opcode == Opcode.BINARY:
                    return frame.data

                """
                # Handle control frames, these are here for the future references.
                elif frame.opcode == Opcode.CLOSE:
                    close_info = Close.parse(frame.data)
                    print(f"Connection closed by client: {close_info.code}, {close_info.reason}")
                    # Send a close frame in response if not already sent
                    if self.protocol.state == self.protocol.OPEN:
                        self.protocol.send_close()
                elif frame.opcode == Opcode.PING:
                    # Respond to ping with pong
                    self.protocol.send_pong(frame.data)
                elif frame.opcode == Opcode.PONG:
                    print("Received pong")
                """
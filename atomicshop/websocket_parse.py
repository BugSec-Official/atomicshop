from typing import Union, Generator
import logging

from websockets.server import ServerProtocol
from websockets.client import ClientProtocol
from websockets.extensions.permessage_deflate import PerMessageDeflate, ServerPerMessageDeflateFactory, ClientPerMessageDeflateFactory
from websockets.http11 import Request, Response
from websockets.frames import Frame, Opcode
from websockets.uri import parse_uri
from websockets.exceptions import InvalidHeaderValue
from websockets.protocol import OPEN
from websockets.streams import StreamReader
from websockets.exceptions import ProtocolError, PayloadTooBig


class WebsocketParseWrongOpcode(Exception):
    pass


def create_byte_http_response(
        byte_http_request: Union[bytes, bytearray],
        enable_logging: bool = False
) -> bytes:
    """
    Create a byte HTTP response from a byte HTTP request.

    Parameters:
    - byte_http_request (bytes, bytearray): The byte HTTP request.
    - enable_logging (bool): Whether to enable logging.

    Returns:
    - bytes: The byte HTTP response.
    """

    # Set up extensions
    permessage_deflate_factory = ServerPerMessageDeflateFactory()

    # Create the protocol instance
    protocol = ServerProtocol(
        extensions=[permessage_deflate_factory],
    )
    # At this state the protocol.state is State.CONNECTING

    if enable_logging:
        logging.basicConfig(level=logging.DEBUG)
        protocol.logger.setLevel(logging.DEBUG)


    protocol.receive_data(byte_http_request)
    events = protocol.events_received()
    event = events[0]
    if isinstance(event, Request):
        # Accept the handshake.
        # After the response is sent, it means the handshake was successful, the protocol.state is State.OPEN
        # Only after this state we can parse frames.
        response = protocol.accept(event)
        return response.serialize()
    else:
        raise ValueError("The event is not a Request object.")


class WebsocketFrameParser:
    def __init__(self):
        # Instantiate the permessage-deflate extension.
        # If a frame uses 'deflate', then the 'permessage_deflate' should be the same object during parsing of
        # several message on the same socket. Each time 'PerMessageDeflate' is initiated, the context changes
        # and more than one message can't be parsed.
        self.permessage_deflate_masked = PerMessageDeflate(
            remote_no_context_takeover=False,
            local_no_context_takeover=False,
            remote_max_window_bits=15,
            local_max_window_bits=15,
        )

        # We need separate instances for masked (frames from client) and unmasked (frames from server).
        self.permessage_deflate_unmasked = PerMessageDeflate(
            remote_no_context_takeover=False,
            local_no_context_takeover=False,
            remote_max_window_bits=15,
            local_max_window_bits=15,
        )

    def parse_frame_bytes(
            self,
            data_bytes: bytes
    ):
        # Define the read_exact function
        def read_exact(n: int) -> Generator[None, None, bytes]:
            return reader.read_exact(n)

        # Helper function to run generator-based coroutines
        def run_coroutine(coroutine):
            try:
                while True:
                    next(coroutine)
            except StopIteration as e:
                return e.value
            except Exception as e:
                raise e  # Re-raise exceptions to be handled by the caller

        # Function to parse frames
        def parse_frame(mask: bool, deflate: bool):
            try:
                if mask:
                    # Decide whether to include permessage-deflate extension
                    extensions = [self.permessage_deflate_masked] if deflate else []
                else:
                    extensions = [self.permessage_deflate_unmasked] if deflate else []

                # Use Frame.parse to parse the frame
                frame_parser = Frame.parse(
                    read_exact,
                    mask=mask,  # Client frames are masked
                    max_size=None,
                    extensions=extensions
                )
                current_frame = run_coroutine(frame_parser)
            except EOFError as e:
                # Not enough data to parse a complete frame
                raise e
            except (ProtocolError, PayloadTooBig) as e:
                print("Error parsing frame:", e)
                raise e
            except Exception as e:
                print("Error parsing frame:", e)
                raise e
            return current_frame

        def process_frame(current_frame):
            if current_frame.opcode == Opcode.TEXT:
                message = current_frame.data.decode('utf-8', errors='replace')
                return message
            elif current_frame.opcode == Opcode.BINARY:
                return current_frame.data
            elif current_frame.opcode == Opcode.CLOSE:
                print("Received close frame")
            elif current_frame.opcode == Opcode.PING:
                print("Received ping")
            elif current_frame.opcode == Opcode.PONG:
                print("Received pong")
            else:
                raise WebsocketParseWrongOpcode("Received unknown frame with opcode:", current_frame.opcode)

        # Create the StreamReader instance
        reader = StreamReader()

        masked = is_frame_masked(data_bytes)
        deflated = is_frame_deflated(data_bytes)

        # Feed the data into the reader
        reader.feed_data(data_bytes)

        # Parse and process frames
        frame = parse_frame(masked, deflated)
        result = process_frame(frame)

        # This is basically not needed since we restart the 'reader = StreamReader()' each function execution.
        # # After processing, reset the reader's buffer
        # reader.buffer = b''

        return result


def create_websocket_frame(
            data: Union[str, bytes, bytearray],
            deflate: bool = False,
            mask: bool = False,
            opcode: int = None
    ) -> bytes:
    """
    Create a WebSocket frame with the given data, optionally applying
    permessage-deflate compression and masking.

    Parameters:
    - data (str, bytes, bytearray): The payload data.
        If str, it will be encoded to bytes using UTF-8.
    - deflate (bool): Whether to apply permessage-deflate compression.
    - mask (bool): Whether to apply masking to the frame.
    - opcode (int): The opcode of the frame. If not provided, it will be
        determined based on the type of data.
        Example:
            from websockets.frames import Opcode
            Opcode.TEXT, Opcode.BINARY, Opcode.CLOSE, Opcode.PING, Opcode.PONG.

    Returns:
    - bytes: The serialized WebSocket frame ready to be sent.
    """

    # Determine the opcode if not provided
    if opcode is None:
        if isinstance(data, str):
            opcode = Opcode.TEXT
        elif isinstance(data, (bytes, bytearray)):
            opcode = Opcode.BINARY
        else:
            raise TypeError("Data must be of type str, bytes, or bytearray.")
    else:
        if not isinstance(opcode, int):
            raise TypeError("Opcode must be an integer.")
        if not isinstance(data, (str, bytes, bytearray)):
            raise TypeError("Data must be of type str, bytes, or bytearray.")

    # Encode string data if necessary
    if isinstance(data, str):
        payload = data.encode('utf-8')
    else:
        payload = bytes(data)

    # Create the Frame instance
    frame = Frame(opcode=opcode, data=payload)

    # Set up extensions if deflate is True
    extensions = []
    if deflate:
        permessage_deflate = PerMessageDeflate(
            remote_no_context_takeover=False,
            local_no_context_takeover=False,
            remote_max_window_bits=15,
            local_max_window_bits=15,
        )
        extensions.append(permessage_deflate)

    # Serialize the frame with the specified options
    try:
        frame_bytes = frame.serialize(
            mask=mask,
            extensions=extensions,
        )
    except Exception as e:
        raise RuntimeError(f"Error serializing frame: {e}")

    return frame_bytes


def is_frame_masked(frame_bytes):
    """
    Determine whether a WebSocket frame is masked.

    Parameters:
    - frame_bytes (bytes): The raw bytes of the WebSocket frame.

    Returns:
    - bool: True if the frame is masked, False otherwise.
    """
    if len(frame_bytes) < 2:
        raise ValueError("Frame is too short to determine masking.")

    # The second byte of the frame header contains the MASK bit
    second_byte = frame_bytes[1]

    # The MASK bit is the most significant bit (MSB) of the second byte
    mask_bit = (second_byte & 0x80) != 0  # 0x80 is 1000 0000 in binary

    return mask_bit


def is_frame_deflated(frame_bytes):
    """
    Determine whether a WebSocket frame is deflated (compressed).

    Parameters:
    - frame_bytes (bytes): The raw bytes of the WebSocket frame.

    Returns:
    - bool: True if the frame is deflated (compressed), False otherwise.
    """
    if len(frame_bytes) < 1:
        raise ValueError("Frame is too short to determine deflation status.")

    # The first byte of the frame header contains the RSV1 bit
    first_byte = frame_bytes[0]

    # The RSV1 bit is the second most significant bit (bit 6)
    rsv1 = (first_byte & 0x40) != 0  # 0x40 is 0100 0000 in binary

    return rsv1


class _WebsocketRequestParse:
    """
    THIS IS ONLY FOR THE REFERENCE IT IS NOT CURRENTLY USED OR SHOULD BE USED.
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


class _WebsocketResponseParse:
    """
    THIS IS ONLY FOR THE REFERENCE IT IS NOT CURRENTLY USED OR SHOULD BE USED.
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
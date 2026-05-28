from typing import Union
from collections.abc import Iterator
import logging

from websockets.server import ServerProtocol
from websockets.extensions.permessage_deflate import PerMessageDeflate, ServerPerMessageDeflateFactory
from websockets.http11 import Request
from websockets.frames import Frame, Opcode
from websockets.streams import StreamReader


class WebsocketParseWrongOpcode(Exception):
    pass


# === Sans-IO frame assembly (RFC 6455 §5) ===
# Buffer raw bytes, parse frame headers, assemble fragmented messages,
# emit raw frame bytes per logical message. Wire-byte fidelity preserved
# (no unmasking, no decompression). Pair with WebsocketFrameParser below
# for payload decoding.


class WebsocketMessageAssembler:
    """
    Sans-IO assembler: feed bytes -> yield raw wire bytes per logical message.

    Fragmented data messages (TEXT/BINARY FIN=0 + CONTINUATION + ... +
    CONTINUATION FIN=1) are concatenated into one emission. Control frames
    (CLOSE/PING/PONG) emit immediately even mid-fragment.

    Emitted bytes are exactly the bytes received -- no unmasking, no
    decompression. Pass through WebsocketFrameParser for payload decoding.
    """

    def __init__(self):
        self._buffer = bytearray()
        self._partial = bytearray()  # Accumulator for fragmented messages.

    def feed(self, chunk: bytes) -> Iterator[bytes]:
        """Push chunk; yield zero or more complete logical messages as raw frame bytes."""
        self._buffer.extend(chunk)
        while True:
            frame = self._try_one_frame()
            if frame is None:
                return
            opcode, fin, frame_bytes = frame
            # Control frames are non-fragmentable; emit immediately even mid-data-fragment.
            if opcode in (Opcode.CLOSE, Opcode.PING, Opcode.PONG):
                yield frame_bytes
                continue
            # Data frame: TEXT / BINARY start a message; CONT extends it.
            if opcode in (Opcode.TEXT, Opcode.BINARY):
                self._partial = bytearray(frame_bytes)
            elif opcode == Opcode.CONT:
                self._partial.extend(frame_bytes)
            else:
                # Unknown opcode -- pass through as standalone frame.
                yield frame_bytes
                continue
            if fin:
                yield bytes(self._partial)
                self._partial.clear()

    @property
    def buffered(self) -> bytes:
        # Mid-fragment payload + mid-frame parse buffer; truthy = partial in progress.
        return bytes(self._partial) + bytes(self._buffer)

    def _try_one_frame(self) -> Union[tuple[int, bool, bytes], None]:
        """Parse one full frame from self._buffer. Return (opcode, fin, frame_bytes) or None if incomplete."""
        buf = self._buffer
        n = len(buf)
        if n < 2:
            return None
        b0 = buf[0]
        b1 = buf[1]
        fin = bool(b0 & 0x80)
        opcode = b0 & 0x0F
        masked = bool(b1 & 0x80)
        length = b1 & 0x7F
        pos = 2
        # Extended payload length (16 or 64 bit).
        if length == 126:
            if n < 4:
                return None
            length, pos = int.from_bytes(buf[2:4], 'big'), 4
        elif length == 127:
            if n < 10:
                return None
            length, pos = int.from_bytes(buf[2:10], 'big'), 10
        # Optional 4-byte masking key.
        if masked:
            if n < pos + 4:
                return None
            pos += 4
        # Full frame length includes header + payload.
        total = pos + length
        if n < total:
            return None
        frame_bytes = bytes(buf[:total])
        del buf[:total]
        return (opcode, fin, frame_bytes)


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
        # Sans-IO generator drive: next() until StopIteration carries the parsed Frame.
        def run_coroutine(gen):
            try:
                while True:
                    next(gen)
            except StopIteration as e:
                return e.value

        def process_frame(current_frame):
            if current_frame.opcode == Opcode.TEXT:
                message = current_frame.data.decode('utf-8', errors='replace')
                return message, 'TEXT'
            elif current_frame.opcode == Opcode.BINARY:
                return current_frame.data, 'BINARY'
            elif current_frame.opcode == Opcode.CLOSE:
                return current_frame.data, 'CLOSE'
            elif current_frame.opcode == Opcode.PING:
                return current_frame.data, 'PING'
            elif current_frame.opcode == Opcode.PONG:
                return current_frame.data, 'PONG'
            else:
                raise WebsocketParseWrongOpcode("Received unknown frame with opcode:", current_frame.opcode)

        masked = is_frame_masked(data_bytes)
        deflated = is_frame_deflated(data_bytes)

        # Per-direction deflate context: client frames (masked) vs server frames (unmasked).
        if deflated:
            extensions = [self.permessage_deflate_masked if masked else self.permessage_deflate_unmasked]
        else:
            extensions = []

        reader = StreamReader()
        reader.feed_data(data_bytes)
        reader.feed_eof()

        # EOFError / ProtocolError / PayloadTooBig propagate to the caller.
        frame = run_coroutine(Frame.parse(
            reader.read_exact,
            mask=masked,
            max_size=None,
            extensions=extensions,
        ))
        parsed_frame, frame_opcode = process_frame(frame)

        return {
            'is_deflated': deflated,
            'is_masked': masked,
            'frame': parsed_frame,
            'opcode': frame_opcode,
        }


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


def is_frame_masked(frame_bytes: bytes):
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


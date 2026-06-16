from collections.abc import Iterator

from hyperframe.frame import Frame, HeadersFrame, DataFrame

from ...protocol_parsers.http2 import HTTP2_CLIENT_PREFACE, HTTP2_FRAME_HEADER_LEN
from .base import Direction, Framer


class Http2Framer(Framer):
    """HTTP/2 frame-boundary framer. Emits wire-fidelity byte slices on END_STREAM."""

    def __init__(self, direction: Direction):
        self._parse_buf = bytearray()
        self._wire_buf = bytearray()
        self._wire_cursor: int = 0
        # Preface only appears in the c2s direction.
        self._preface_seen: bool = direction != 'client_to_server'

    def consume(self, chunk: bytes) -> list[bytes]:
        self._wire_buf.extend(chunk)
        self._parse_buf.extend(chunk)
        return list(self._extract_messages())

    @property
    def buffered(self) -> bytes:
        """Wire bytes received since the last emit — partial-message-in-flight."""
        return bytes(self._wire_buf)

    # --- internals ---

    def _extract_messages(self) -> Iterator[bytes]:
        if not self._preface_seen:
            if len(self._parse_buf) < len(HTTP2_CLIENT_PREFACE):
                return
            # Skip even on mismatch; better to keep parsing downstream frames than stall.
            del self._parse_buf[:len(HTTP2_CLIENT_PREFACE)]
            self._wire_cursor += len(HTTP2_CLIENT_PREFACE)
            self._preface_seen = True

        while len(self._parse_buf) >= HTTP2_FRAME_HEADER_LEN:
            frame, length = Frame.parse_frame_header(memoryview(self._parse_buf[:HTTP2_FRAME_HEADER_LEN]))
            total = HTTP2_FRAME_HEADER_LEN + length
            if len(self._parse_buf) < total:
                return
            del self._parse_buf[:total]
            self._wire_cursor += total
            # END_STREAM on HEADERS or DATA closes the stream — cut wire slice here.
            if isinstance(frame, (HeadersFrame, DataFrame)) and 'END_STREAM' in frame.flags:
                wire_slice = bytes(self._wire_buf[:self._wire_cursor])
                del self._wire_buf[:self._wire_cursor]
                self._wire_cursor = 0
                yield wire_slice

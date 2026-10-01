from collections.abc import Iterator

from hyperframe.frame import (
    Frame, HeadersFrame, ContinuationFrame, PushPromiseFrame, DataFrame, RstStreamFrame)

from ...protocol_parsers.http2 import HTTP2_CLIENT_PREFACE, HTTP2_FRAME_HEADER_LEN
from .base import Direction, Framer


# Frames that carry a stream's message (header block / body); everything else is control.
_MESSAGE_FRAMES = (HeadersFrame, ContinuationFrame, PushPromiseFrame, DataFrame)


class Http2Framer(Framer):
    """HTTP/2 frame-boundary framer. Emits wire-fidelity byte slices: one per ended stream, one per control frame."""

    def __init__(self, direction: Direction):
        self._parse_buf = bytearray()  # Bytes not yet parsed into whole frames.
        self._pending = bytearray()  # Whole frames of the slice in progress, wire order.
        self._pending_streams: set[int] = set()  # Stream ids with frames in _pending.
        self._end_at_end_headers: set[int] = set()  # HEADERS(END_STREAM) whose block continues in CONTINUATION.
        self._prefix = bytearray()  # Client preface; rides on the next emitted slice.
        # Preface only appears in the c2s direction.
        self._preface_seen: bool = direction != 'client_to_server'

    def consume(self, chunk: bytes) -> list[bytes]:
        self._parse_buf.extend(chunk)
        return list(self._extract_messages())

    @property
    def buffered(self) -> bytes:
        """Wire bytes received since the last emit — partial-message-in-flight."""
        return bytes(self._prefix + self._pending + self._parse_buf)

    # --- internals ---

    def _extract_messages(self) -> Iterator[bytes]:
        if not self._preface_seen:
            if len(self._parse_buf) < len(HTTP2_CLIENT_PREFACE):
                return
            # Skip even on mismatch; better to keep parsing downstream frames than stall.
            self._prefix += self._parse_buf[:len(HTTP2_CLIENT_PREFACE)]
            del self._parse_buf[:len(HTTP2_CLIENT_PREFACE)]
            self._preface_seen = True

        while len(self._parse_buf) >= HTTP2_FRAME_HEADER_LEN:
            frame, length = Frame.parse_frame_header(memoryview(self._parse_buf[:HTTP2_FRAME_HEADER_LEN]))
            total = HTTP2_FRAME_HEADER_LEN + length
            if len(self._parse_buf) < total:
                return
            frame_bytes = bytes(self._parse_buf[:total])
            del self._parse_buf[:total]

            # Control frame (stream-0, or WINDOW_UPDATE/PRIORITY/RST of a stream with nothing buffered):
            # relay alone at once, ahead of any partial message — never cut a message around it.
            # Safe to reorder: carries no HPACK state.
            if not isinstance(frame, _MESSAGE_FRAMES) and frame.stream_id not in self._pending_streams:
                yield self._emit(frame_bytes)
                continue

            self._pending += frame_bytes
            self._pending_streams.add(frame.stream_id)
            # Cut at a stream's last frame. Interleaved streams cut in wire order (a later
            # header block may index HPACK entries an earlier one added — never reorder them).
            if self._ends_stream(frame):
                wire_slice = bytes(self._pending)
                self._pending.clear()
                self._pending_streams.clear()
                yield self._emit(wire_slice)

    def _emit(self, wire_slice: bytes) -> bytes:
        """Prepend the client preface to the first emitted slice."""
        if not self._prefix:
            return wire_slice
        wire_slice = bytes(self._prefix) + wire_slice
        self._prefix.clear()
        return wire_slice

    def _ends_stream(self, frame: Frame) -> bool:
        """True for a stream's last frame: RST_STREAM, or END_STREAM (applied at END_HEADERS for a header block)."""
        sid = frame.stream_id
        if isinstance(frame, RstStreamFrame):
            self._end_at_end_headers.discard(sid)
            return True
        if isinstance(frame, DataFrame):
            return 'END_STREAM' in frame.flags
        if isinstance(frame, HeadersFrame) and 'END_STREAM' in frame.flags:
            if 'END_HEADERS' in frame.flags:
                return True
            self._end_at_end_headers.add(sid)
            return False
        if isinstance(frame, ContinuationFrame) and 'END_HEADERS' in frame.flags and sid in self._end_at_end_headers:
            self._end_at_end_headers.discard(sid)
            return True
        return False

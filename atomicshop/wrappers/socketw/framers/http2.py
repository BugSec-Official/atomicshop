from collections.abc import Iterator
from dataclasses import dataclass, field

from hyperframe.frame import (
    Frame, HeadersFrame, ContinuationFrame, DataFrame, RstStreamFrame,
)

from .base import Framer


_CLIENT_PREFACE = b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'
_FRAME_HEADER_LEN = 9


@dataclass
class _StreamState:
    headers: bytearray = field(default_factory=bytearray)
    data: bytearray = field(default_factory=bytearray)


class Http2Framer(Framer):
    """HTTP/2 frame-boundary framer. Emits HPACK-encoded headers + DATA per stream on END_STREAM."""

    def __init__(self, is_client_to_server: bool):
        self._buffer = bytearray()
        self._streams: dict[int, _StreamState] = {}
        # Preface only appears in the client->server direction.
        self._preface_seen: bool = not is_client_to_server

    def consume(self, chunk: bytes) -> Iterator[bytes]:
        self._buffer.extend(chunk)
        yield from self._extract_messages()

    @property
    def buffered(self) -> bytes:
        """In-flight per-stream buffers + unparsed bytes; concat for partial-in-progress signal."""
        out = bytearray()
        for sid in sorted(self._streams):
            s = self._streams[sid]
            out.extend(s.headers)
            out.extend(s.data)
        out.extend(self._buffer)
        return bytes(out)

    # --- frame parsing ---

    def _extract_messages(self) -> Iterator[bytes]:
        if not self._preface_seen:
            if len(self._buffer) < len(_CLIENT_PREFACE):
                return
            # Skip even on mismatch; better to keep parsing downstream frames than stall.
            del self._buffer[:len(_CLIENT_PREFACE)]
            self._preface_seen = True

        while len(self._buffer) >= _FRAME_HEADER_LEN:
            frame, length = Frame.parse_frame_header(memoryview(self._buffer[:_FRAME_HEADER_LEN]))
            total = _FRAME_HEADER_LEN + length
            if len(self._buffer) < total:
                return
            payload = bytes(self._buffer[_FRAME_HEADER_LEN:total])
            del self._buffer[:total]
            frame.parse_body(memoryview(payload))
            msg = self._handle(frame)
            if msg is not None:
                yield msg

    def _handle(self, frame: Frame) -> bytes | None:
        sid = frame.stream_id
        if isinstance(frame, HeadersFrame):
            state = self._streams.setdefault(sid, _StreamState())
            state.headers.extend(frame.data)
            if 'END_STREAM' in frame.flags:
                return self._emit(sid)
        elif isinstance(frame, ContinuationFrame):
            state = self._streams.get(sid)
            if state is not None:
                state.headers.extend(frame.data)
        elif isinstance(frame, DataFrame):
            state = self._streams.get(sid)
            if state is None:
                return None  # DATA on RST'd / unknown stream; ignore.
            state.data.extend(frame.data)
            if 'END_STREAM' in frame.flags:
                return self._emit(sid)
        elif isinstance(frame, RstStreamFrame):
            self._streams.pop(sid, None)
        # SETTINGS / PING / WINDOW_UPDATE / GOAWAY / PRIORITY / PUSH_PROMISE: ignored.
        return None

    def _emit(self, sid: int) -> bytes | None:
        s = self._streams.pop(sid, None)
        if s is None:
            return None
        # Raw HPACK-encoded header block + concatenated DATA payloads.
        return bytes(s.headers) + bytes(s.data)

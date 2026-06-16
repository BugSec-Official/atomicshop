from collections.abc import Iterator

from websockets.frames import Opcode

from ...protocol_parsers.websocket import parse_frame_header
from .base import Direction, Framer


# === WebSocket framer (RFC 6455 §5) ===
# Assemble fragmented data messages (TEXT/BINARY + CONT... FIN); control frames
# (CLOSE/PING/PONG) pass through even mid-fragment. Wire bytes preserved exactly
# (no unmask, no decompress). Pair with protocol_parsers.websocket.WebsocketFrameParser for payload decoding.

class WebSocketFramer(Framer):
    """WebSocket frame-boundary framer; emits raw wire bytes per logical message."""

    def __init__(self, direction: Direction):
        # direction unused: mask bit is read per-frame. Param kept for interface uniformity.
        del direction
        self._parse_buf = bytearray()
        self._wire_buf = bytearray()  # Fragment accumulator (in-progress logical message).

    def consume(self, chunk: bytes) -> list[bytes]:
        self._parse_buf.extend(chunk)
        return list(self._extract_messages())

    @property
    def buffered(self) -> bytes:
        # Mid-fragment payload + mid-frame parse leftover; truthy = partial in progress.
        return bytes(self._wire_buf) + bytes(self._parse_buf)

    # --- internals ---

    def _extract_messages(self) -> Iterator[bytes]:
        while True:
            parsed = parse_frame_header(self._parse_buf)
            if parsed is None:
                return
            opcode, fin, total = parsed
            if len(self._parse_buf) < total:
                return
            frame_bytes = bytes(self._parse_buf[:total])
            del self._parse_buf[:total]
            # Control frames are non-fragmentable; emit immediately even mid-data-fragment.
            if opcode in (Opcode.CLOSE, Opcode.PING, Opcode.PONG):
                yield frame_bytes
                continue
            if opcode in (Opcode.TEXT, Opcode.BINARY):
                self._wire_buf = bytearray(frame_bytes)
            elif opcode == Opcode.CONT:
                self._wire_buf.extend(frame_bytes)
            else:
                yield frame_bytes  # Unknown opcode — pass through standalone.
                continue
            if fin:
                yield bytes(self._wire_buf)
                self._wire_buf.clear()

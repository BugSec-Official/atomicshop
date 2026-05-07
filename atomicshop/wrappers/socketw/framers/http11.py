import h11
from collections import deque
from collections.abc import Iterator
from typing import Literal

from .base import Framer


Role = Literal['request', 'response']


# === HTTP/1.1 framer ===
# Bidirectional parser driven one-sided: each completed message is followed
# by a stub event on the unsent side so the parser returns to IDLE for the
# next message. Response role also needs the request method (body-elision
# rules for HEAD / 204 / 304); supplied via set_pending_request_method.
# Wire fidelity: bytes mirrored in _wire_buf; emitted slice = total - trailing.

class Http11Framer(Framer):
    """HTTP/1.1 framer (request|response role); emits raw wire bytes per message."""

    def __init__(self, role: Role):
        if role not in ('request', 'response'):
            raise ValueError(f"role must be 'request' or 'response', got {role!r}")
        our_role = h11.SERVER if role == 'request' else h11.CLIENT
        self.role: Role = role
        self._conn = h11.Connection(our_role=our_role)
        self._wire_buf = bytearray()
        self._method_fifo: deque[str] = deque()
        self._fake_sent = False

    def consume(self, chunk: bytes) -> Iterator[bytes]:
        if not chunk:
            return
        self._wire_buf.extend(chunk)
        self._conn.receive_data(chunk)
        yield from self._drain_events()

    def finish(self) -> Iterator[bytes]:
        """Drain on EOF; yield any final message (body-until-close)."""
        try:
            self._conn.receive_data(b'')
            yield from self._drain_events()
        except h11.RemoteProtocolError:
            # Truncation: receiver inspects .buffered and raises PeerClosedMidMessage.
            return

    @property
    def buffered(self) -> bytes:
        return bytes(self._wire_buf)

    def set_pending_request_method(self, method: str) -> None:
        """FIFO request method (response role only); pops on each completed response."""
        self._method_fifo.append((method or '').upper())
        if self.role == 'response' and not self._fake_sent and self._conn.our_state is h11.IDLE:
            self._inject_request()

    # --- internals ---

    def _drain_events(self) -> Iterator[bytes]:
        while True:
            ev = self._conn.next_event()
            if ev is h11.NEED_DATA or ev is h11.PAUSED:
                return
            if isinstance(ev, h11.ConnectionClosed):
                return  # Post-EOF event keeps repeating; ignore.
            if isinstance(ev, h11.EndOfMessage):
                yield self._cut_message()

    def _cut_message(self) -> bytes:
        leftover = self._conn.trailing_data[0]
        consumed = len(self._wire_buf) - len(leftover)
        msg = bytes(self._wire_buf[:consumed])
        del self._wire_buf[:consumed]

        if self._conn.their_state is not h11.DONE:
            return msg  # 1xx interim; outer loop continues.

        if self.role == 'request':
            # Advance to DONE with a stub Response; bytes discarded.
            self._conn.send(h11.Response(status_code=200, headers=[(b'Content-Length', b'0')]))
            self._conn.send(h11.EndOfMessage())
        else:  # response
            if self._method_fifo:
                self._method_fifo.popleft()
            self._fake_sent = False

        if self._conn.our_state is h11.DONE:
            self._conn.start_next_cycle()
            if self.role == 'response' and self._method_fifo:
                self._inject_request()

        return msg

    def _inject_request(self) -> None:
        # Stub Request informs the parser of the next request method (body-elision rules).
        method = self._method_fifo[0]
        self._conn.send(h11.Request(method=method, target=b'/', headers=[(b'Host', b'x')]))
        self._conn.send(h11.EndOfMessage())
        self._fake_sent = True

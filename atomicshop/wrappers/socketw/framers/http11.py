import h11
from collections import deque
from collections.abc import Iterator
from typing import Literal

from .base import Framer


# === HTTP/1.1 framer ===
# Bidirectional parser driven one-sided: each completed message is followed
# by a stub event on the unsent side so the parser returns to IDLE for the
# next message. The 'response' role also needs the request method (body-elision
# rules for HEAD / 204 / 304): the request side enqueues via
# set_pending_request_method, the response side's consume() primes h11 —
# h11.Connection stays single-threaded.
# Wire fidelity: bytes mirrored in _wire_buf; emitted slice = total - trailing.

class Http11Framer(Framer):
    """HTTP/1.1 framer; emits raw wire bytes per message. `role` picks the h11
    side ('request' -> SERVER, 'response' -> CLIENT), decoupled from the wire leg."""

    def __init__(self, role: Literal['request', 'response']):
        if role not in ('request', 'response'):
            raise ValueError(f"role must be 'request' or 'response', got {role!r}")
        our_role = h11.SERVER if role == 'request' else h11.CLIENT
        self._role: Literal['request', 'response'] = role
        self._conn = h11.Connection(our_role=our_role)
        self._wire_buf = bytearray()
        self._method_fifo: deque[str] = deque()
        self._fake_sent = False

    def consume(self, chunk: bytes) -> list[bytes]:
        # Prime h11 before feeding bytes; 'response' role only (single-threaded
        # _conn). Inject every fresh cycle, not only when a method is queued: h11
        # reads a Response even from SERVER IDLE, so a skipped inject desyncs the
        # halves and the next (Request, CLIENT) hits a non-IDLE SERVER -> KeyError.
        if (self._role == 'response'
                and not self._fake_sent
                and self._conn.our_state is h11.IDLE):
            self._inject_request()
        self._wire_buf.extend(chunk)
        self._conn.receive_data(chunk)
        return list(self._drain_events())

    def finish(self) -> list[bytes]:
        """Drain on EOF; return any final message (body-until-close)."""
        try:
            self._conn.receive_data(b'')
            return list(self._drain_events())
        except h11.RemoteProtocolError:
            # Truncation: receiver inspects .buffered and raises PeerClosedMidMessage.
            return []

    @property
    def buffered(self) -> bytes:
        return bytes(self._wire_buf)

    def set_pending_request_method(self, method: str) -> None:
        """FIFO request method ('response' role only); pops on each completed response."""
        # Called from the request side's thread; deque.append is atomic under the GIL.
        # h11 priming runs on the response side's thread in consume().
        self._method_fifo.append((method or '').upper())

    # --- internals ---

    def _drain_events(self) -> Iterator[bytes]:
        while True:
            ev = self._conn.next_event()
            if ev is h11.NEED_DATA or ev is h11.PAUSED:
                return
            if isinstance(ev, h11.ConnectionClosed):
                return  # Post-EOF event keeps repeating; ignore.
            # InformationalResponse (1xx) is emitted standalone — no EndOfMessage
            # follows. Yield it so the MITM can parse/forward each response separately;
            # _cut_message's their_state != DONE guard skips the next-cycle advance.
            if isinstance(ev, (h11.InformationalResponse, h11.EndOfMessage)):
                yield self._cut_message()

    def _cut_message(self) -> bytes:
        """Slice off bytes for the just-completed message; advance state if final."""
        leftover = self._conn.trailing_data[0]
        consumed = len(self._wire_buf) - len(leftover)
        msg = bytes(self._wire_buf[:consumed])
        del self._wire_buf[:consumed]
        if self._conn.their_state is h11.DONE:
            self._advance_to_next_message()
        return msg  # their_state != DONE: 1xx interim (SEND_RESPONSE/SWITCHED_PROTOCOL) or body-until-close (CLOSED); no advance.

    def _advance_to_next_message(self) -> None:
        """Stub the unsent side to DONE; start_next_cycle; inject pending request if any."""
        if self._role == 'request':
            self._inject_response_stub()
        else:  # 'response'
            if self._method_fifo:
                self._method_fifo.popleft()
            self._fake_sent = False

        if self._conn.our_state is h11.DONE:
            self._conn.start_next_cycle()
            if self._role == 'response' and self._method_fifo:
                self._inject_request()

    def _inject_request(self) -> None:
        """Stub h11.Request (body-elision rules + 101 acceptance via Upgrade proposal)."""
        # No queued method (handoff race / dropped first request): GET keeps h11
        # synced; only HEAD would change body-elision, and a miss is rare.
        method = self._method_fifo[0] if self._method_fifo else 'GET'
        # Upgrade headers let h11 accept a 101 Switching Protocols response;
        # h11 doesn't enforce that the server's Upgrade value matches the proposal.
        self._conn.send(h11.Request(method=method, target=b'/', headers=[
            (b'Host', b'x'),
            (b'Connection', b'Upgrade'),
            (b'Upgrade', b'websocket'),
        ]))
        self._conn.send(h11.EndOfMessage())
        self._fake_sent = True

    def _inject_response_stub(self) -> None:
        """Stub h11.Response to advance our side to DONE; bytes discarded."""
        self._conn.send(h11.Response(status_code=200, headers=[(b'Content-Length', b'0')]))
        self._conn.send(h11.EndOfMessage())

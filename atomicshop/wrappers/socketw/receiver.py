import logging
import queue
import socket
import ssl
from collections.abc import Callable

import h11
import select
from collections import deque
from pathlib import Path

from ..loggingw import loggingw
from .framers.base import Framer


# === Receive-path exceptions ===
# Stdlib socket / TLS exceptions flow through unchanged. Receive-path failures
# carry partial bytes via exc.received. PeerClosedMidMessage is the only custom
# one — represents framer-level truncation with no stdlib equivalent.
class PeerClosedMidMessage(ConnectionError):
    """Peer closed while a framer had a partial (truncated) message."""


def recv_exact(
        client_socket: socket.socket,
        bytes_amount: int,
        timeout: float | None = None
) -> bytes:
    """
    Read exactly bytes_amount bytes, looping over short recv() returns.

    Used by the sans-IO accept path: ClientHello bytes are consumed into a
    buffer for inspection and re-injected via MemoryBIO during the real TLS
    handshake. recv(N) is allowed to return fewer than N bytes (common for
    fragmented ClientHellos under TLS 1.3 with PQ key shares), so a loop is
    required. Per-recv timeout via settimeout(); EOF mid-read raises
    ConnectionError because a half-record is unusable downstream.
    """
    if bytes_amount < 1:
        raise ValueError(f"recv_exact: bytes_amount must be >= 1, got {bytes_amount}")

    previous_timeout: float | None = client_socket.gettimeout()
    client_socket.settimeout(timeout)
    buffer: bytearray = bytearray()
    try:
        while len(buffer) < bytes_amount:
            try:
                chunk: bytes = client_socket.recv(bytes_amount - len(buffer))
            except socket.timeout:
                # Normalize to stdlib TimeoutError.
                raise TimeoutError(
                    f"recv_exact: timed out after {len(buffer)}/{bytes_amount} bytes")
            if chunk == b'':
                raise ConnectionError(
                    f"recv_exact: peer closed after {len(buffer)}/{bytes_amount} bytes")
            buffer.extend(chunk)
    finally:
        client_socket.settimeout(previous_timeout)
    return bytes(buffer)


def is_socket_ready_for_read(socket_instance: socket.socket | ssl.SSLSocket, timeout: float = 0) -> bool:
    """Return True if the socket has bytes ready (or buffered TLS plaintext)."""
    if socket_instance.fileno() == -1:
        return False
    # pending() first: select() only sees the OS buffer, but TLS plaintext
    # can sit in OpenSSL's user-space buffer after a multi-record recv.
    if hasattr(socket_instance, 'pending') and socket_instance.pending() > 0:
        return True
    readable, _, _ = select.select([socket_instance], [], [], timeout)
    return bool(readable)


class Receiver:
    """
    Receive bytes from one direction of a TLS / TCP socket; report EOF / errors.

    Two modes:
      * framer is not None  -> protocol mode: block on recv, feed framer, emit
        when framer reports a complete message.
      * framer is None      -> unframed mode: recv and sniff for a known protocol;
        on a hit upgrade to a framer (protocol mode), else relay opaquely,
        delimiting on an idle-quiet tick (idle_seconds) or EOF.

    Construct once per direction per connection and reuse across receive cycles —
    re-creating per cycle creates child loggers under a global lock. Peer address
    is cached at construction so the recv path is the only thing that can fail.
    """
    def __init__(
            self,
            ssl_socket: ssl.SSLSocket,
            logger: logging.Logger | None = None,
            framer: Framer | None = None,
            idle_seconds: float = 0.5,
            protocol_detector: Callable[[bytes], Framer | None] | None = None,
            max_probe_bytes: int = 1024,
    ):
        self.ssl_socket: ssl.SSLSocket = ssl_socket
        self.buffer_size_receive: int = 16384
        self._framer: Framer | None = framer
        self._idle_seconds: float = idle_seconds
        self._unframed_buffer: bytearray = bytearray()  # unframed mode only
        # Optional sniffer; called on each unframed-mode chunk with the accumulated buffer.
        # Returns the matching Framer when detection succeeds, None when uncertain.
        # Receiver enforces byte / idle-quiet caps: either exhausting max_probe_bytes
        # or hitting an idle-quiet tick without a match disables the detector and
        # flushes the buffer as one opaque message.
        self._protocol_detector: Callable[[bytes], Framer | None] | None = protocol_detector
        self._max_probe_bytes: int = max_probe_bytes
        # Framer output queue. One recv() can emit several complete messages at once (HTTP/1.1
        # pipelining, coalesced records); receive() pops one per call.
        # deque is used since the mechanism is FIFO and popleft is used to get and remove
        # the first element, which is O(1) on deque, unlike O(n) on list.
        self._framed_messages: deque[bytes] = deque()
        # Cross-thread framer swap channel. set_framer enqueues from any thread;
        # _apply_pending_framer_swap drains and applies on the owning thread so _framer,
        # _unframed_buffer, and _framed_messages stay single-threaded.
        self._pending_framer_queue: queue.Queue = queue.Queue()
        # Cross-thread request-method channel (HTTP/1.1 HEAD/204/304 body-elision).
        # The opposite leg can push a method before this leg's framer exists
        # (reversed orientation: the server's first request is parsed first); held
        # here, applied to the framer on creation so the first response frames right.
        self._pending_request_methods: queue.Queue = queue.Queue()

        peer = ssl_socket.getpeername()  # Cache once; recv path is the only failure surface.
        self.peer_address: str = peer[0]
        self.peer_port: int = peer[1]

        if logger is not None:
            self.logger: logging.Logger = loggingw.get_logger_with_level(f'{logger.name}.{Path(__file__).stem}')
        else:
            self.logger = logging.getLogger(__name__)

    def set_framer(self, framer: Framer | None) -> None:
        """Request a framer swap from any thread; applied on the owning thread before its next consume."""
        # E.g. HTTP/1.1 -> WebSocket after 101: Http11Framer.buffered holds the first WS
        # frame bytes if they arrived in the same recv chunk as the 101. None resets to unframed mode.
        self._pending_framer_queue.put(framer)

    def set_pending_request_method(self, method: str) -> None:
        """Hand a request method to this leg's response framer (HTTP/1.1 body-elision).
        Called from the opposite (request-reading) thread."""
        framer = self._framer
        if framer is None:
            # Framer not built yet (reversed orientation): hold until creation.
            self._pending_request_methods.put(method)
        elif hasattr(framer, 'set_pending_request_method'):
            framer.set_pending_request_method(method)
        # else: framer doesn't track methods (HTTP/2, MQTT, WebSocket) — drop.

    def _apply_pending_framer_swap(self) -> None:
        """Owning-thread only: drain the swap queue and apply each request in order."""
        while True:
            try:
                new_framer: Framer | None = self._pending_framer_queue.get_nowait()
            except queue.Empty:
                return
            self._do_set_framer(new_framer)

    def _apply_pending_request_methods(self) -> None:
        """Owning-thread only: forward methods held before the framer existed."""
        framer = self._framer
        if framer is None:
            return  # No framer yet; keep holding.
        supports: bool = hasattr(framer, 'set_pending_request_method')
        while True:
            try:
                method: str = self._pending_request_methods.get_nowait()
            except queue.Empty:
                return
            if supports:
                framer.set_pending_request_method(method)
            # else: drain-and-drop; framer doesn't track methods.

    def _do_set_framer(self, framer: Framer | None) -> None:
        """Owning-thread only: actual framer swap; migrates trailing wire bytes across the boundary."""
        leftover: bytes = (
            self._framer.buffered if self._framer is not None else bytes(self._unframed_buffer))
        self._framer = framer
        self._unframed_buffer.clear()
        self._framed_messages.clear()
        # Hand off any methods held while the framer didn't exist, before the
        # leftover (which may be this leg's first response) is framed.
        self._apply_pending_request_methods()
        if not leftover:
            return
        if framer is not None:
            self._framed_messages.extend(framer.consume(leftover))
        else:
            self._unframed_buffer.extend(leftover)

    def receive(self) -> bytes:
        """
        Receive one complete logical message.

        Returns bytes (b'' = clean peer EOF). Raises stdlib ConnectionError,
        ssl.SSLError, TimeoutError, InterruptedError, or PeerClosedMidMessage
        on failure. Receive-path failures carry any partial bytes as
        exc.received.
        """
        self.logger.info(f"Waiting for data from {self.peer_address}:{self.peer_port}")

        # Apply any framer swap another thread requested via set_framer (e.g. HTTP/1.1 upgrade ->
        # WebSocket after a 101) before choosing framed vs. unframed mode for this cycle.
        self._apply_pending_framer_swap()
        # Forward any request methods held before the framer existed (or that landed
        # in the gap between framer creation and its swap-drain).
        self._apply_pending_request_methods()
        if self._framer is None:
            data: bytes = self._recv_message_unframed()
        else:
            data: bytes = self._recv_message_protocol()
        if data:
            self.logger.info(f"Received: {data[0:100]}...")  # Full message logged elsewhere.

        return data

    # === Protocol mode ===

    def _recv_message_protocol(self) -> bytes:
        """Block on recv, consume bytes, return one complete message or b'' on clean EOF."""
        assert self._framer is not None, "_recv_message_protocol requires a framer"

        while True:
            # Are there any ready fully framed messages available?
            if self._framed_messages:
                # If so, get + remove the first message from deque and return it. This is O(1) on deque, unlike O(n) on list.
                msg: bytes = self._framed_messages.popleft()
                self.logger.info(f"Received total: [{len(msg)}] bytes")
                return msg

            # Since there are no readily framed messages, we will receive the buffer from socket.
            chunk: bytes = self._recv_chunk()
            # If the socket was closed by the peer
            if chunk == b'':
                # we will initiate protocol EOF.
                return self._handle_protocol_eof()

            # Apply any framer swap another thread requested via set_framer during the blocking recv
            # (e.g. HTTP/1.1 upgrade -> WebSocket after a 101), so this chunk goes through the right framer.
            self._apply_pending_framer_swap()
            framer = self._framer
            assert framer is not None, "framer swap to None mid-protocol-loop is unsupported"

            # 'framer.consume(chunk)' should return a fully framed message if the current chunk is enough to complete one
            # or an empty list if the chunk is not enough to complete a message.
            # If there are multiple messages in the chunk, it should return all of them.
            try:
                complete_framed_messages: list[bytes] = framer.consume(chunk)
            except h11.RemoteProtocolError as exc:
                # Sniffer's guess was wrong (or the upstream is non-conformant). Drop the
                # framer, migrate its buffered bytes (which include this chunk) to the
                # unframed buffer, disable detection, fall through as opaque passthrough.
                self.logger.info(
                    f"Framer raised {type(exc).__name__}: {exc}; degrading to passthrough.")
                self._do_set_framer(None)
                self._protocol_detector = None
                if self._unframed_buffer:
                    return self._flush_unframed_buffer()
                return self._recv_message_unframed()
            self._framed_messages.extend(complete_framed_messages)

    def _handle_protocol_eof(self) -> bytes:
        """
        On peer EOF: emit final message (body-until-close), raise on truncation, or return b''.
        """
        framer = self._framer
        assert framer is not None, "_handle_protocol_eof requires a framer"

        # Get the full framed messages.
        final_framed_messages: list[bytes] = framer.finish()
        self._framed_messages.extend(final_framed_messages)

        # If there are any available-framed messages, return them
        if self._framed_messages:
            msg: bytes = self._framed_messages.popleft()
            self.logger.info(f"Received total: [{len(msg)}] bytes")
            return msg

        # Were there any partial message received, that still weren't cut to fully framed messages?
        if framer.buffered:
            # If so, use that as the partial bytes for the PeerClosedMidMessage exception,
            # which represents a truncation that doesn't have a stdlib equivalent.
            exc: PeerClosedMidMessage = PeerClosedMidMessage("Peer closed mid-message (truncated).")
            exc.received = framer.buffered
            raise exc

        self.logger.info("Peer closed connection (clean EOF).")
        return b''

    # === Unframed mode (no framer: detect, else opaque passthrough) ===
    def _recv_message_unframed(self) -> bytes:
        """No framer yet: recv and sniff for a known protocol and upgrade on a hit;
        else relay opaquely, delimiting on an idle-quiet tick (idle_seconds) or EOF."""
        while True:
            # Apply any framer swap another thread requested via set_framer (e.g. HTTP/1.1 upgrade ->
            # WebSocket after a 101); transition to protocol mode if one landed.
            self._apply_pending_framer_swap()
            if self._framer is not None:
                # _do_set_framer already migrated the unframed buffer through the new framer.
                return self._recv_message_protocol()
            if is_socket_ready_for_read(self.ssl_socket, timeout=self._idle_seconds):
                chunk: bytes = self._recv_chunk()
                if chunk == b'':
                    # EOF: flush any buffered bytes, else clean close.
                    if self._unframed_buffer:
                        return self._flush_unframed_buffer()
                    self.logger.info("Peer closed connection (clean EOF).")
                    return b''
                self._unframed_buffer.extend(chunk)
                # Sniff for a known protocol; on hit, _do_set_framer migrates the
                # buffered bytes through the new framer (preserves wire order).
                if self._protocol_detector is not None:
                    detected = self._protocol_detector(bytes(self._unframed_buffer))
                    if detected is not None:
                        self._do_set_framer(detected)
                        return self._recv_message_protocol()
                    if len(self._unframed_buffer) >= self._max_probe_bytes:
                        # Byte cap: give up; flush as one opaque message, switch to passthrough.
                        self._protocol_detector = None
                        return self._flush_unframed_buffer()
            elif self._unframed_buffer:
                # Quiet tick with buffered bytes -> message boundary. Also gives the
                # detector its time-cap: if it hasn't decided by now, it never will.
                if self._protocol_detector is not None:
                    self._protocol_detector = None
                return self._flush_unframed_buffer()
            # else: quiet with empty buffer; keep polling.

    def _flush_unframed_buffer(self) -> bytes:
        msg: bytes = bytes(self._unframed_buffer)
        self._unframed_buffer.clear()
        self.logger.info(f"Received total: [{len(msg)}] bytes")
        return msg

    # === Shared ===

    def _recv_chunk(self) -> bytes:
        """recv() once; on failure, attach any partial bytes via exc.received."""
        try:
            return self.ssl_socket.recv(self.buffer_size_receive)
        except (ConnectionError, ssl.SSLError, TimeoutError, InterruptedError) as exc:
            exc.received = self._drain_partial_bytes()
            raise

    def _drain_partial_bytes(self) -> bytes:
        """Return partial bytes from whichever buffer is active (read-only on framer; clears unframed buffer)."""
        if self._framer is not None:
            return self._framer.buffered
        out: bytes = bytes(self._unframed_buffer)
        self._unframed_buffer.clear()
        return out

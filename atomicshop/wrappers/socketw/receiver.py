import logging
import socket
import ssl

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
        client_socket,
        bytes_amount: int,
        timeout: float = None
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

    previous_timeout = client_socket.gettimeout()
    client_socket.settimeout(timeout)
    buffer = bytearray()
    try:
        while len(buffer) < bytes_amount:
            try:
                chunk = client_socket.recv(bytes_amount - len(buffer))
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


def is_socket_ready_for_read(socket_instance, timeout: float = 0) -> bool:
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
      * framer is None      -> time-based mode: poll with select, accumulate
        bytes, emit on the first quiet tick (idle_seconds) or on EOF.

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
    ):
        self.ssl_socket: ssl.SSLSocket = ssl_socket
        self.buffer_size_receive: int = 16384
        self._framer = framer
        self._idle_seconds: float = idle_seconds
        self._idle_buffer: bytearray = bytearray()  # time-based mode only
        self._pending: deque[bytes] = deque()       # protocol mode: pipelined messages from prior consume()

        peer = ssl_socket.getpeername()  # Cache once; recv path is the only failure surface.
        self.peer_address: str = peer[0]
        self.peer_port: int = peer[1]

        if logger is not None:
            self.logger: logging.Logger = loggingw.get_logger_with_level(f'{logger.name}.{Path(__file__).stem}')
        else:
            self.logger = logging.getLogger(__name__)

    def set_framer(self, framer: Framer | None) -> None:
        """Swap framer mid-connection (e.g., HTTP/1.1 Upgrade -> WebSocket). None resets to time-based mode."""
        self._framer = framer
        self._idle_buffer.clear()
        self._pending.clear()

    def receive(self) -> bytes:
        """
        Receive one complete logical message.

        Returns bytes (b'' = clean peer EOF). Raises stdlib ConnectionError,
        ssl.SSLError, TimeoutError, InterruptedError, or PeerClosedMidMessage
        on failure. Receive-path failures carry any partial bytes as
        exc.received.
        """
        self.logger.info(f"Waiting for data from {self.peer_address}:{self.peer_port}")
        if self._framer is None:
            data = self._recv_message_idle()
        else:
            data = self._recv_message_protocol()
        if data:
            self.logger.info(f"Received: {data[0:100]}...")  # Full message logged elsewhere.
        return data

    # === Protocol mode ===

    def _recv_message_protocol(self) -> bytes:
        """Block on recv, consume bytes, return one complete message or b'' on clean EOF."""
        while True:
            if self._pending:
                msg = self._pending.popleft()
                self.logger.info(f"Received total: [{len(msg)}] bytes")
                return msg
            chunk = self._safe_recv_chunk()
            if chunk == b'':
                return self._handle_protocol_eof()
            self._pending.extend(self._framer.consume(chunk))

    def _handle_protocol_eof(self) -> bytes:
        """On peer EOF: emit final message (body-until-close), raise on truncation, or return b''."""
        self._pending.extend(self._framer.finish())
        if self._pending:
            msg = self._pending.popleft()
            self.logger.info(f"Received total: [{len(msg)}] bytes")
            return msg
        if self._framer.buffered:
            exc = PeerClosedMidMessage("Peer closed mid-message (truncated).")
            exc.received = self._framer.buffered
            raise exc
        self.logger.info("Peer closed connection (clean EOF).")
        return b''

    # === Time-based mode (no protocol framer) ===

    def _recv_message_idle(self) -> bytes:
        """Poll with select; emit buffered bytes on first quiet tick or on EOF."""
        while True:
            if is_socket_ready_for_read(self.ssl_socket, timeout=self._idle_seconds):
                chunk = self._safe_recv_chunk()
                if chunk == b'':
                    # EOF: flush any buffered bytes, else clean close.
                    if self._idle_buffer:
                        return self._flush_idle_buffer()
                    self.logger.info("Peer closed connection (clean EOF).")
                    return b''
                self._idle_buffer.extend(chunk)
            elif self._idle_buffer:
                # Quiet with buffered bytes -> message boundary.
                return self._flush_idle_buffer()
            # else: quiet with empty buffer; keep polling.

    def _flush_idle_buffer(self) -> bytes:
        msg = bytes(self._idle_buffer)
        self._idle_buffer.clear()
        self.logger.info(f"Received total: [{len(msg)}] bytes")
        return msg

    # === Shared ===

    def _safe_recv_chunk(self) -> bytes:
        """recv() once; on failure, attach any partial bytes via exc.received."""
        try:
            return self.ssl_socket.recv(self.buffer_size_receive)
        except (ConnectionError, ssl.SSLError, TimeoutError, InterruptedError) as exc:
            exc.received = self._drain_partial_bytes()
            raise

    def _drain_partial_bytes(self) -> bytes:
        """Return partial bytes from whichever buffer is active (read-only on framer; clears idle buffer)."""
        if self._framer is not None:
            return self._framer.buffered
        out = bytes(self._idle_buffer)
        self._idle_buffer.clear()
        return out

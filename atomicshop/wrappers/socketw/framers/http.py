from collections import deque

from ...protocol_parsers.http2 import HTTP2_CLIENT_PREFACE
from .base import Direction, Framer
from .http11 import Http11Framer
from .http2 import Http2Framer
from .sniffer import SharedProtocolState


# === HTTP/1.1 vs HTTP/2 dispatcher ===
# Sniffer commits to "HTTP-shaped" without picking a wire version; this thin
# wrapper peeks the first chunk for the HTTP/2 client preface and delegates
# to Http11Framer or Http2Framer for the rest of the connection. s2c side
# follows the shared state set by c2s (HTTP/2 has no server preface).


class HttpFramer(Framer):
    """Delegating framer that resolves to Http11Framer or Http2Framer on the first chunk."""

    def __init__(self, direction: Direction, shared: SharedProtocolState | None = None):
        self._direction: Direction = direction
        self._shared: SharedProtocolState | None = shared
        self._delegate: Framer | None = None
        self._buf: bytearray = bytearray()
        self._pending_methods: deque[str] = deque()  # queued before delegate is chosen

    def consume(self, chunk: bytes) -> list[bytes]:
        if self._delegate is not None:
            return self._delegate.consume(chunk)
        self._buf.extend(chunk)
        self._try_decide()
        if self._delegate is None:
            return []
        # Just resolved: forward queued request methods, then migrate buffered bytes.
        while self._pending_methods:
            method = self._pending_methods.popleft()
            if hasattr(self._delegate, 'set_pending_request_method'):
                self._delegate.set_pending_request_method(method)
        buffered = bytes(self._buf)
        self._buf.clear()
        return self._delegate.consume(buffered)

    def finish(self) -> list[bytes]:
        if self._delegate is None:
            return []
        return self._delegate.finish()

    @property
    def buffered(self) -> bytes:
        if self._delegate is not None:
            return self._delegate.buffered
        return bytes(self._buf)

    def set_pending_request_method(self, method: str) -> None:
        """Queue the method for the s2c response framer; forwarded once the delegate is chosen."""
        if self._delegate is None:
            self._pending_methods.append(method)
        elif hasattr(self._delegate, 'set_pending_request_method'):
            self._delegate.set_pending_request_method(method)

    # --- internals ---

    def _http11(self) -> Http11Framer:
        """Build the HTTP/1.1 delegate with the h11 role for this leg, from the
        detected orientation (request_side); defaults to normal if undetected."""
        request_side = (self._shared.request_side if self._shared else None) or 'client_to_server'
        role = 'request' if self._direction == request_side else 'response'
        return Http11Framer(role=role)

    def _try_decide(self) -> None:
        if self._shared is not None and self._shared.http_version == 'http2':
            self._delegate = Http2Framer(direction=self._direction)
            return
        if self._shared is not None and self._shared.http_version == 'http1':
            self._delegate = self._http11()
            return
        if self._direction == 'server_to_client':
            # No HTTP/2 server preface exists; default to HTTP/1.1 once enough bytes
            # arrive. If we're wrong about HTTP/2, Http11Framer will RemoteProtocolError
            # and Receiver re-detects.
            if len(self._buf) >= 8:
                self._delegate = self._http11()
                if self._shared is not None:
                    self._shared.set_http_version('http1')
            return
        # c2s: look for the 24-byte HTTP/2 client preface.
        if len(self._buf) >= len(HTTP2_CLIENT_PREFACE):
            if bytes(self._buf[:len(HTTP2_CLIENT_PREFACE)]) == HTTP2_CLIENT_PREFACE:
                self._delegate = Http2Framer(direction=self._direction)
                ver = 'http2'
            else:
                self._delegate = self._http11()
                ver = 'http1'
            if self._shared is not None:
                self._shared.set_http_version(ver)
            return
        # < 24 bytes: rule out preface only if the first byte differs.
        if self._buf and self._buf[:1] != b'P':
            self._delegate = self._http11()
            if self._shared is not None:
                self._shared.set_http_version('http1')

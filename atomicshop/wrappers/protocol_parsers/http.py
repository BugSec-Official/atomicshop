"""HTTP/1.1 sans-IO parser; h11-driven."""

import http

import h11


# === Public helpers ===

def get_request_methods() -> list[str]:
    """All HTTP request method tokens."""
    # noinspection PyUnresolvedReferences
    return [method.value for method in http.HTTPMethod]


def is_first_bytes_http_request(request_bytes: bytes) -> bool:
    """Leading bytes match an HTTP method token."""
    if not request_bytes:
        return False
    for method in get_request_methods():
        if request_bytes.startswith(method.encode()):
            return True
    return False


def is_first_bytes_http_response(response_bytes: bytes) -> bool:
    """Leading bytes match 'HTTP/' status line."""
    if not response_bytes:
        return False
    return response_bytes.startswith(b'HTTP/')


# === Signature detection ===
# Tri-state: True = match, False = mismatch, None = need more bytes. Side-agnostic:
# orientation is decided by which shape a leg shows, not by which leg it is.

def detect_http_request_line(buf: bytes) -> bool | None:
    """Permissive request-line shape (method token); strict parsing left to h11.
    Misclassification triggers receiver re-detection."""
    if len(buf) < 3:
        return None
    if buf.startswith(b'SSH'):
        return False
    if not buf[:3].isalpha():
        return False
    if b' ' not in buf:
        if len(buf) >= 16:
            return False  # no space within 16 bytes — too long for an HTTP method token
        return None
    space_pos = buf.find(b' ')
    newline_pos = buf.find(b'\n')
    if newline_pos != -1 and space_pos > newline_pos:
        return False
    return True


def detect_http_response_line(buf: bytes) -> bool | None:
    """HTTP/1.x status line ('HTTP/' prefix)."""
    if len(buf) < 7:
        return None
    return buf.startswith(b'HTTP/')


# === Headers ===
# h11 lowercases header names; this wrapper restores case-insensitive lookup
# so callers can use 'Content-Length' / 'Upgrade' / 'Sec-WebSocket-Protocol'.

class _Headers(dict):
    """Case-insensitive str→str header dict; stored keys are lowercase."""

    def __init__(self, items=()):
        super().__init__()
        for k, v in items:
            super().__setitem__(self._k(k), v)

    @staticmethod
    def _k(key):
        return key.lower() if isinstance(key, str) else key

    def __contains__(self, key):
        return super().__contains__(self._k(key))

    def __getitem__(self, key):
        return super().__getitem__(self._k(key))

    def get(self, key, default=None):
        return super().get(self._k(key), default)


def _h11_headers_to_dict(h11_headers) -> _Headers:
    return _Headers((k.decode('latin-1'), v.decode('latin-1')) for k, v in h11_headers)


def _drain(conn) -> tuple[object | None, bytes, str | None]:
    """Pull h11 events; return (head_event, body, err). Head captured even if body errors (HEAD-style)."""
    body: list[bytes] = []
    head = None
    try:
        while True:
            ev = conn.next_event()
            if ev is h11.NEED_DATA or isinstance(ev, h11.ConnectionClosed):
                break
            if isinstance(ev, (h11.Request, h11.Response, h11.InformationalResponse)):
                head = ev
                if isinstance(ev, h11.InformationalResponse):
                    return head, b'', None  # 1xx: no body, no EndOfMessage follows.
            elif isinstance(ev, h11.Data):
                body.append(bytes(ev.data))
            elif isinstance(ev, h11.EndOfMessage):
                break
    except h11.RemoteProtocolError as e:
        return head, b''.join(body), str(e)
    return head, b''.join(body), None


# === Request parser ===

class HTTPRequestParse:
    """HTTP/1.1 request parser. Duck-typed: .command/.path/.request_version/.headers/.body."""

    def __init__(self, request_bytes: bytes):
        self.request_bytes: bytes = request_bytes
        self.command: str | None = None
        self.path: str | None = None
        self.request_version: str | None = None
        self.headers: _Headers = _Headers()
        self.body: bytes | None = None
        self.content_length: int | None = None
        self.error_message: str | None = None

    def parse(self) -> tuple['HTTPRequestParse', bool, str]:
        """Return (self, is_http, error_str). is_http=False on non-HTTP or parse error."""
        if not is_first_bytes_http_request(self.request_bytes):
            return self, False, "HTTP Request Parsing: Not HTTP request by first bytes."

        conn = h11.Connection(our_role=h11.SERVER)
        try:
            conn.receive_data(self.request_bytes)
            conn.receive_data(b'')  # EOF: completes body-until-close cases.
        except h11.RemoteProtocolError as e:
            self.error_message = f"Bad request: {e}"
            return self, False, f"HTTP Request Parsing: {self.error_message}"

        head, body, err = _drain(conn)
        if not isinstance(head, h11.Request):
            self.error_message = f"Bad request: {err or 'no request line'}"
            return self, False, f"HTTP Request Parsing: {self.error_message}"

        self.command = head.method.decode('ascii').upper()
        self.path = head.target.decode('ascii', errors='replace')
        self.request_version = f"HTTP/{head.http_version.decode('ascii')}"
        self.headers = _h11_headers_to_dict(head.headers)
        self.body = body
        cl = self.headers.get('content-length')
        if cl is not None:
            try:
                self.content_length = int(cl)
            except ValueError:
                pass
        return self, True, ''


# === Response parser ===

class HTTPResponseParse:
    """HTTP/1.1 response parser. Duck-typed: .code/.status/.headers/.body."""

    def __init__(self, response_raw_bytes: bytes):
        self.response_raw_bytes: bytes = response_raw_bytes
        # .code mirrors http.client.HTTPResponse: int after begin(); 0 before/on failure.
        self.code: int = 0
        self.status: int = 0
        self.reason: str = ''
        self.response_version: str | None = None
        self.headers: _Headers = _Headers()
        self.body: bytes | None = None
        self.content_length: int | None = None
        self.error: str | None = None
        self.is_http: bool = False

    def parse(self) -> tuple['HTTPResponseParse | None', bool, str | None]:
        """Return (self_or_None, is_http, error). None on first-byte rejection (old contract)."""
        if not is_first_bytes_http_response(self.response_raw_bytes):
            self.error = "HTTP Response Parsing: Not a valid HTTP Response by first bytes."
            return None, False, self.error

        # h11 CLIENT needs a sent Request before parsing a Response; stub GET (bytes
        # discarded) with Upgrade proposal so 101 Switching Protocols is accepted.
        # Standalone parse has no method context — HEAD-style responses (CL set, empty
        # body) raise on body collection; _drain returns the head event regardless.
        conn = h11.Connection(our_role=h11.CLIENT)
        try:
            conn.send(h11.Request(method=b'GET', target=b'/', headers=[
                (b'Host', b'x'),
                (b'Connection', b'Upgrade'),
                (b'Upgrade', b'websocket'),
            ]))
            conn.send(h11.EndOfMessage())
            conn.receive_data(self.response_raw_bytes)
            conn.receive_data(b'')
        except (h11.LocalProtocolError, h11.RemoteProtocolError) as e:
            self.error = f"HTTP Response Parsing: Not a valid HTTP Response: {e}"
            return None, False, self.error

        head, body, _ = _drain(conn)
        if not isinstance(head, (h11.Response, h11.InformationalResponse)):
            self.error = "HTTP Response Parsing: Not a valid HTTP Response: no status line"
            return None, False, self.error

        self.code = head.status_code
        self.status = head.status_code
        self.reason = head.reason.decode('latin-1') if head.reason else ''
        self.response_version = f"HTTP/{head.http_version.decode('ascii')}"
        self.headers = _h11_headers_to_dict(head.headers)
        self.body = body
        cl = self.headers.get('content-length')
        if cl is not None:
            try:
                self.content_length = int(cl)
            except ValueError:
                pass
        self.is_http = True
        return self, True, None

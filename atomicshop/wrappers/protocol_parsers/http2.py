"""HTTP/2 autoparsing for the MITM pipeline.

Mirrors sibling `http` module: per-direction parser objects that turn raw
HTTP/2 wire bytes (yielded by Http2Framer at END_STREAM) into duck-typed
request/response objects compatible with `client_message.request_auto_parsed`
and `response_auto_parsed`.

Why hyperframe+hpack instead of the higher-level h2 library: h2 enforces full
state-machine semantics (e.g. "the server side cannot initiate odd-numbered
streams"). That's correct for an active HTTP/2 endpoint but wrong for a
passive proxy observer — when we parse server-to-client bytes we see HEADERS
on stream IDs the real client opened on the other socket, not our state.
hyperframe and hpack — the libraries h2 itself uses underneath — give us
frame parsing and HPACK decoding without role-validation, which is exactly
what the autoparser needs.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field

import hpack
import hyperframe.frame


HTTP2_FRAME_HEADER_LEN = 9
HTTP2_CLIENT_PREFACE = b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'


@dataclass(slots=True)
class _StreamAccum:
    """Per-stream scratch; HEADERS + DATA frames merge here until END_STREAM."""
    headers: list[tuple[str, str]] = field(default_factory=list)
    body: bytearray = field(default_factory=bytearray)
    trailers: list[tuple[str, str]] = field(default_factory=list)
    pending_block: bytearray = field(default_factory=bytearray)  # for CONTINUATION
    end_stream: bool = False
    in_header_block: bool = False  # True between HEADERS(END_HEADERS=0) and CONTINUATION(END_HEADERS=1)


def _split_headers(headers):
    """Partition (key, value) tuples into pseudo (':...') and regular dicts."""
    pseudo: dict[str, str] = {}
    regular: dict[str, str] = {}
    for k, v in headers:
        (pseudo if k.startswith(':') else regular)[k] = v
    return pseudo, regular


def _peek_status(headers) -> int | None:
    """Return the :status code as int, or None if missing/non-numeric."""
    for k, v in headers:
        if k == ':status':
            return int(v) if v.isdigit() else None
    return None


class Http2RequestParse:
    """HTTP/2 request, duck-typed to HTTPRequestParse: .command/.path/.headers/.body."""

    def __init__(self, headers, body, trailers, stream_id):
        pseudo, regular = _split_headers(headers)
        self.pseudo_headers: dict[str, str] = pseudo
        self.command: str = pseudo.get(':method', '').upper()
        self.path: str = pseudo.get(':path', '')
        self.authority: str = pseudo.get(':authority', '')
        self.scheme: str = pseudo.get(':scheme', '')
        self.headers: dict[str, str] = regular
        self.body: bytes = bytes(body)
        self.trailers: dict[str, str] = {k: v for k, v in trailers}
        self.stream_id: int = stream_id
        # Ordered, case-preserving wire view for semantic validation (dicts above lose both).
        self.raw_headers: list[tuple[str, str]] = list(headers)
        self.raw_trailers: list[tuple[str, str]] = list(trailers)


class Http2ResponseParse:
    """HTTP/2 response, duck-typed to HTTPResponseParse: .code/.headers/.body."""

    def __init__(self, headers, body, trailers, stream_id):
        pseudo, regular = _split_headers(headers)
        self.pseudo_headers: dict[str, str] = pseudo
        status = pseudo.get(':status', '0')
        self.code: int = int(status) if status.isdigit() else 0
        self.headers: dict[str, str] = regular
        self.body: bytes = bytes(body)
        self.trailers: dict[str, str] = {k: v for k, v in trailers}
        self.stream_id: int = stream_id
        self.path: str = ''  # filled by parse_http from the request-side FIFO
        # Ordered, case-preserving wire view for semantic validation (dicts above lose both).
        self.raw_headers: list[tuple[str, str]] = list(headers)
        self.raw_trailers: list[tuple[str, str]] = list(trailers)


class Http2DirectionParser:
    """Sans-io HTTP/2 autoparser for one direction; feed() yields one parsed object per END_STREAM.

    Uses hyperframe for frame parsing and hpack for header decoding — the HPACK
    decoder table is connection-scoped, so this object lives for the whole leg.
    The instance is read-only on the wire: we never produce frames, the proxy
    forwards the peer's own frames on the opposite socket.
    """

    def __init__(self, is_request_side: bool, state: 'Http2ConnectionState | None' = None):
        self._is_request_side = is_request_side
        self._state = state  # observed client SETTINGS land here when state is provided
        self._decoder = hpack.Decoder()
        self._buf = bytearray()
        # Connection preface is only sent by the client (request side).
        self._preface_seen = not is_request_side
        self._streams: dict[int, _StreamAccum] = {}

    def feed(self, raw_bytes: bytes) -> Iterator[Http2RequestParse | Http2ResponseParse]:
        if not raw_bytes:
            return
        self._buf.extend(raw_bytes)

        if not self._preface_seen:
            if len(self._buf) < len(HTTP2_CLIENT_PREFACE):
                return
            # Skip even on mismatch — keep parsing, the connection is what it is.
            del self._buf[:len(HTTP2_CLIENT_PREFACE)]
            self._preface_seen = True

        while len(self._buf) >= HTTP2_FRAME_HEADER_LEN:
            frame, length = hyperframe.frame.Frame.parse_frame_header(
                memoryview(self._buf[:HTTP2_FRAME_HEADER_LEN]))
            total = HTTP2_FRAME_HEADER_LEN + length
            if len(self._buf) < total:
                return
            frame.parse_body(memoryview(self._buf[HTTP2_FRAME_HEADER_LEN:total]))
            del self._buf[:total]
            yield from self._on_frame(frame)

    def _on_frame(self, frame) -> Iterator[Http2RequestParse | Http2ResponseParse]:
        sid = frame.stream_id
        flags = frame.flags

        if isinstance(frame, hyperframe.frame.RstStreamFrame):
            self._streams.pop(sid, None)
            return

        if isinstance(frame, hyperframe.frame.HeadersFrame):
            accum = self._streams.setdefault(sid, _StreamAccum())
            accum.pending_block.extend(frame.data)
            if 'END_STREAM' in flags:
                accum.end_stream = True
            if 'END_HEADERS' in flags:
                yield from self._decode_pending(accum, sid)
                accum.in_header_block = False
            else:
                accum.in_header_block = True
        elif isinstance(frame, hyperframe.frame.ContinuationFrame):
            accum = self._streams.setdefault(sid, _StreamAccum())
            accum.pending_block.extend(frame.data)
            if 'END_HEADERS' in flags:
                yield from self._decode_pending(accum, sid)
                accum.in_header_block = False
        elif isinstance(frame, hyperframe.frame.DataFrame):
            accum = self._streams.setdefault(sid, _StreamAccum())
            accum.body.extend(frame.data)
            if 'END_STREAM' in flags:
                accum.end_stream = True
        elif isinstance(frame, hyperframe.frame.SettingsFrame):
            # A peer's non-ACK SETTINGS (either leg) owes an ACK we must send back; the
            # worker drains settings_acks_owed. ACK frames carry no settings, need no reply.
            # Record the client's framing limits (request side) so the response encoder
            # sizes DATA / refuses oversized header blocks.
            # 0x05 = MAX_FRAME_SIZE, 0x06 = MAX_HEADER_LIST_SIZE.
            if self._state is not None and 'ACK' not in flags:
                self._state.settings_acks_owed += 1
                if self._is_request_side:
                    if 0x05 in frame.settings:
                        self._state.max_frame_size = frame.settings[0x05]
                    if 0x06 in frame.settings:
                        self._state.max_header_list_size = frame.settings[0x06]
            return
        else:
            # WINDOW_UPDATE / PING / GOAWAY / PRIORITY / PUSH_PROMISE: ignored.
            return

        accum = self._streams.get(sid)
        if accum is not None and accum.end_stream and not accum.in_header_block:
            self._streams.pop(sid, None)
            cls = Http2RequestParse if self._is_request_side else Http2ResponseParse
            yield cls(accum.headers, accum.body, accum.trailers, sid)

    def _decode_pending(self, accum: _StreamAccum, sid: int) -> Iterator[Http2ResponseParse]:
        """Decode the accumulated HPACK block; yield 1xx interim responses standalone, else store as headers/trailers."""
        decoded = self._decoder.decode(bytes(accum.pending_block))
        accum.pending_block.clear()
        if accum.headers:
            accum.trailers = decoded  # Subsequent block after main headers = trailers.
            return
        # First block on this stream. On the response side, 1xx interims emit standalone
        # so the parsed metadata reflects each response separately. Stream stays open;
        # the final response's headers come in a later HEADERS frame.
        if not self._is_request_side:
            status = _peek_status(decoded)
            if status is not None and 100 <= status < 200:
                yield Http2ResponseParse(decoded, b'', [], sid)
                return
        accum.headers = decoded


# ============================================================================
# Response semantic validation (RFC 9113 §8.1.2/§8.2): rules the permissive
# parser skips, enforced for the responder gate to match h11 on HTTP/1.x.
# ============================================================================

# Connection-specific fields are forbidden on the wire in HTTP/2 (§8.2.2).
_H2_FORBIDDEN_HEADERS = frozenset({
    'connection', 'proxy-connection', 'keep-alive', 'transfer-encoding', 'upgrade'})


def validate_response_headers(raw_headers) -> str | None:
    """Defect string if raw_headers isn't a valid HTTP/2 response header block, else None.

    raw_headers: ordered decoded (name, value) tuples as they arrived on the wire.
    """
    status_count = 0
    seen_regular = False
    for name, value in raw_headers:
        if not name:
            return "empty header field name"
        if name != name.lower():
            return f"field name not lowercase: {name!r}"
        if name[0] == ':':
            if seen_regular:
                return f"pseudo-header {name!r} after a regular header"
            if name != ':status':
                return f"invalid response pseudo-header: {name!r}"
            status_count += 1
            if not (len(value) == 3 and value.isdigit() and 100 <= int(value) <= 599):
                return f"invalid :status value: {value!r}"
        else:
            seen_regular = True
            if name in _H2_FORBIDDEN_HEADERS:
                return f"connection-specific header forbidden in HTTP/2: {name!r}"
            if name == 'te' and value.lower() != 'trailers':
                return f"te header must be 'trailers' in HTTP/2: {value!r}"
    if status_count == 0:
        return "missing :status pseudo-header"
    if status_count > 1:
        return "multiple :status pseudo-headers"
    return None


def validate_response_trailers(raw_trailers) -> str | None:
    """Defect string if raw_trailers carries anything illegal for a trailer block, else None."""
    for name, value in raw_trailers:
        if not name:
            return "empty trailer field name"
        if name != name.lower():
            return f"trailer field name not lowercase: {name!r}"
        if name[0] == ':':
            return f"pseudo-header {name!r} not allowed in trailers"
        if name in _H2_FORBIDDEN_HEADERS:
            return f"connection-specific header forbidden in trailers: {name!r}"
    return None


# ============================================================================
# Encoder side: inverse of Http2DirectionParser.
# Produces HTTP/2 wire bytes (HEADERS + DATA + optional trailers HEADERS) from
# a structured request/response. Used by engines that synthesise responses.
# ============================================================================

_DEFAULT_MAX_FRAME_SIZE = 16384  # HTTP/2 SETTINGS_MAX_FRAME_SIZE default


class Http2ConnectionState:
    """Observed peer SETTINGS + handshake debt, populated by Http2DirectionParser.

    settings_acks_owed counts received non-ACK SETTINGS awaiting our ACK; preface_sent
    tracks whether we've sent our own SETTINGS preface on this leg. The worker drains
    both. HPACK encoder state is intentionally NOT tracked here — _encode_header_block
    uses a per-call encoder with sensitive=True (see its docstring) to keep
    synthesised responses from polluting the client's HPACK dynamic table.
    """
    __slots__ = ('max_frame_size', 'max_header_list_size', 'settings_acks_owed', 'preface_sent')

    def __init__(self):
        self.max_frame_size: int = _DEFAULT_MAX_FRAME_SIZE  # 16384, RFC 7540 §6.5.2
        self.max_header_list_size: int | None = None
        self.settings_acks_owed: int = 0
        self.preface_sent: bool = False


def _encode_header_block(headers) -> bytes:
    """HPACK-encode headers as never-indexed literals — zero dynamic-table churn.

    Each header is flagged sensitive=True so neither sender nor receiver
    indexes it. This keeps a synthesised response from polluting the client's
    HPACK dynamic table, which protects HPACK state on connections that mix
    synthesised and forwarded responses.
    """
    encoder = hpack.Encoder()
    return encoder.encode([(k, v, True) for k, v in headers])


# === Stream-0 control frames: the proxy terminates the SETTINGS handshake per leg ===

def encode_http2_settings(settings: dict[int, int] | None = None) -> bytes:
    """Serialize a non-ACK SETTINGS frame (stream 0) — the proxy's own preface/update."""
    sf = hyperframe.frame.SettingsFrame(stream_id=0)
    sf.settings = dict(settings or {})
    return sf.serialize()


def encode_http2_settings_ack() -> bytes:
    """Serialize an empty SETTINGS frame with ACK set — acknowledges a peer's SETTINGS."""
    sf = hyperframe.frame.SettingsFrame(stream_id=0)
    sf.flags.add('ACK')
    return sf.serialize()


def settings_handshake_output(
        state: Http2ConnectionState, *,
        include_preface: bool, local_settings: dict[int, int] | None = None) -> bytes:
    """Stream-0 bytes the proxy owes on a leg: its own preface SETTINGS once (when
    include_preface), then one ACK per received non-ACK SETTINGS. Drains the state."""
    out = bytearray()
    if include_preface and not state.preface_sent:
        out += encode_http2_settings(local_settings)
        state.preface_sent = True
    for _ in range(state.settings_acks_owed):
        out += encode_http2_settings_ack()
    state.settings_acks_owed = 0
    return bytes(out)


def offline_client_output(
        state: Http2ConnectionState, responder_messages, *, is_http2: bool) -> list:
    """Offline send list for the client: prefix the owed stream-0 handshake (preface
    once + ACKs) ahead of the responder's HTTP/2 reply, so the client gets a server
    preface and its SETTINGS is ACKed. Non-HTTP/2 connections pass through unchanged."""
    if not is_http2:
        return list(responder_messages)
    handshake = settings_handshake_output(state, include_preface=True)
    return ([handshake] if handshake else []) + list(responder_messages)


def _serialize_data_frames(
        stream_id: int, body: bytes, end_stream: bool,
        max_frame_size: int = _DEFAULT_MAX_FRAME_SIZE) -> bytes:
    """Split body across DATA frames at max_frame_size; END_STREAM on the last."""
    if not body:
        if not end_stream:
            return b''
        df = hyperframe.frame.DataFrame(stream_id=stream_id)
        df.flags.add('END_STREAM')
        return df.serialize()
    out = bytearray()
    n = len(body)
    for i in range(0, n, max_frame_size):
        chunk = body[i:i + max_frame_size]
        df = hyperframe.frame.DataFrame(stream_id=stream_id)
        df.data = chunk
        if end_stream and (i + max_frame_size) >= n:
            df.flags.add('END_STREAM')
        out.extend(df.serialize())
    return bytes(out)


def encode_http2_message(
        pseudo_headers,
        regular_headers,
        body: bytes,
        stream_id: int,
        trailers: dict[str, str] | None = None,
        max_frame_size: int = _DEFAULT_MAX_FRAME_SIZE,
) -> bytes:
    """Encode an HTTP/2 message (request or response) as wire bytes.

    Layout: HEADERS(END_HEADERS) + DATA*(END_STREAM on last when no trailers)
    + optional trailing HEADERS(END_HEADERS, END_STREAM).

    :param pseudo_headers: ordered list of (name, value) ':...' pseudo-headers.
    :param regular_headers: dict[str, str] or list[tuple[str, str]] of regular headers.
    :param body: raw body bytes.
    :param stream_id: HTTP/2 stream id (use the request's stream_id when replying).
    :param trailers: optional dict of trailing headers (emitted as a second HEADERS frame).
    :param max_frame_size: DATA frame size limit; pass the client's negotiated
        SETTINGS_MAX_FRAME_SIZE for faithful framing. Defaults to the SETTINGS default (16384).
    :return: wire bytes ready to send over the client TLS socket.
    """
    regular = list(regular_headers.items()) if isinstance(regular_headers, dict) else list(regular_headers)
    header_block = _encode_header_block(list(pseudo_headers) + regular)

    has_body = bool(body)
    has_trailers = bool(trailers)

    out = bytearray()
    hf = hyperframe.frame.HeadersFrame(stream_id=stream_id)
    hf.data = header_block
    hf.flags.add('END_HEADERS')
    if not has_body and not has_trailers:
        hf.flags.add('END_STREAM')
    out.extend(hf.serialize())

    if has_body:
        out.extend(_serialize_data_frames(
            stream_id, body, end_stream=not has_trailers, max_frame_size=max_frame_size))

    if has_trailers:
        tf = hyperframe.frame.HeadersFrame(stream_id=stream_id)
        tf.data = _encode_header_block(trailers.items())
        tf.flags.add('END_HEADERS')
        tf.flags.add('END_STREAM')
        out.extend(tf.serialize())
    return bytes(out)


def encode_http2_response(
        status_code: int,
        headers=None,
        body: bytes = b'',
        stream_id: int = 0,
        trailers: dict[str, str] | None = None,
        max_frame_size: int = _DEFAULT_MAX_FRAME_SIZE,
) -> bytes:
    """Encode an HTTP/2 response (:status + regular headers + body + optional trailers)."""
    return encode_http2_message(
        [(':status', str(status_code))],
        headers or {},
        body, stream_id, trailers, max_frame_size,
    )


def encode_http2_request(
        method: str,
        path: str,
        authority: str,
        scheme: str = 'https',
        headers=None,
        body: bytes = b'',
        stream_id: int = 1,
        trailers: dict[str, str] | None = None,
        max_frame_size: int = _DEFAULT_MAX_FRAME_SIZE,
) -> bytes:
    """Encode an HTTP/2 request (:method / :scheme / :authority / :path + body + optional trailers)."""
    return encode_http2_message(
        [(':method', method.upper()), (':scheme', scheme),
         (':authority', authority), (':path', path)],
        headers or {},
        body, stream_id, trailers, max_frame_size,
    )

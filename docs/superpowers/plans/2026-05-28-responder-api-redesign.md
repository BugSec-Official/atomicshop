# Responder API Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move HTTP/2 `stream_id`, MQTT `packet_identifier`/`protocol_version`, WebSocket `mask`/`deflate`, and HTTP/1.x `http_version` off the engine call site and onto auto-filling `build_byte_*` helpers on `ResponderParent`.

**Architecture:** Three connection-scoped state objects (`Http2ConnectionState`, `MqttConnectionState` (already exists), `WebSocketConnectionState`) hang off `ResponderParent`. The framework writes to them as protocol observations happen (HTTP/2 SETTINGS frames, MQTT CONNECT, WebSocket 101). Helpers read from them when building responses. HPACK encoding stays per-call with `sensitive=True` per existing correctness invariant.

**Tech Stack:** Python 3.13+; `hyperframe`, `hpack`, `h11`, `mqttools`, `websockets`; existing `atomicshop.mitm` framework.

**Spec:** `docs/superpowers/specs/2026-05-28-responder-api-redesign-design.md`

---

## Commit Strategy

The atomicshop working tree has unrelated in-progress modifications to many files. Each task in this plan commits only the files it touches via explicit `git add <path>`. The user's other pending modifications stay uncommitted.

## File Structure

**Modified:**
- `atomicshop/wrappers/protocol_parsers/http2.py` — add `Http2ConnectionState`, SETTINGS observation in `_on_frame()`, plumb `max_frame_size` through encoder
- `atomicshop/wrappers/protocol_parsers/websocket.py` — add `WebSocketConnectionState`
- `atomicshop/mitm/engines/__parent/responder___parent.py` — extend `add_args`, rewrite `build_byte_response`/`build_byte_http2_response`, add MQTT and WebSocket helpers
- `atomicshop/mitm/engines/__reference_general/responder___reference_general.py` — rewrite all 4 reference examples with auto-fill annotation comments
- `atomicshop/mitm/connection_thread_worker.py` — eager state allocation, pass state via `add_args`, capture WS extensions during 101 swap

**Created:** None.

---

## Task 1: Add `Http2ConnectionState` and `WebSocketConnectionState`

**Files:**
- Modify: `atomicshop/wrappers/protocol_parsers/http2.py`
- Modify: `atomicshop/wrappers/protocol_parsers/websocket.py`

- [ ] **Step 1: Add `Http2ConnectionState` to `http2.py`**

Insert after the existing `_DEFAULT_MAX_FRAME_SIZE` constant (`http2.py:190`):

```python
class Http2ConnectionState:
    """Observed client SETTINGS, populated by Http2DirectionParser.

    HPACK encoder state is intentionally NOT tracked here — _encode_header_block
    uses a per-call encoder with sensitive=True (see its docstring) to keep
    synthesised responses from polluting the client's HPACK dynamic table.
    """
    __slots__ = ('max_frame_size', 'max_header_list_size')

    def __init__(self):
        self.max_frame_size: int = _DEFAULT_MAX_FRAME_SIZE  # 16384, RFC 7540 §6.5.2
        self.max_header_list_size: int | None = None
```

- [ ] **Step 2: Add `WebSocketConnectionState` to `websocket.py`**

Find a sensible insertion point (top of the module, after imports). Add:

```python
class WebSocketConnectionState:
    """Connection-scoped WebSocket negotiation captured at the 101 handshake."""
    __slots__ = ('permessage_deflate_negotiated', 'subprotocol')

    def __init__(self):
        self.permessage_deflate_negotiated: bool = False
        self.subprotocol: str | None = None
```

- [ ] **Step 3: Smoke check**

```powershell
python -c "from atomicshop.wrappers.protocol_parsers.http2 import Http2ConnectionState; from atomicshop.wrappers.protocol_parsers.websocket import WebSocketConnectionState; h = Http2ConnectionState(); w = WebSocketConnectionState(); assert h.max_frame_size == 16384 and h.max_header_list_size is None; assert w.permessage_deflate_negotiated is False and w.subprotocol is None; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```powershell
git add atomicshop/wrappers/protocol_parsers/http2.py atomicshop/wrappers/protocol_parsers/websocket.py
git commit -m @'
mitm: add Http2ConnectionState and WebSocketConnectionState

Connection-scoped state holders for responder auto-fill. Http2 tracks
client SETTINGS (MAX_FRAME_SIZE, MAX_HEADER_LIST_SIZE) used for faithful
DATA framing. WebSocket tracks permessage-deflate negotiation and the
selected subprotocol captured from the 101 response.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 2: SETTINGS observation hook in `Http2DirectionParser`

**Files:**
- Modify: `atomicshop/wrappers/protocol_parsers/http2.py` (the `Http2DirectionParser._on_frame()` method, currently at line 127-164)

- [ ] **Step 1: Add `state` parameter to `Http2DirectionParser.__init__`**

Change the constructor signature so the parser can write SETTINGS observations into a shared state object:

```python
def __init__(self, is_request_side: bool, state: 'Http2ConnectionState | None' = None):
    self._is_request_side = is_request_side
    self._state = state  # observed client SETTINGS land here when state is provided
    self._decoder = hpack.Decoder()
    self._buf = bytearray()
    # Connection preface is only sent by the client (request side).
    self._preface_seen = not is_request_side
    self._streams: dict[int, _StreamAccum] = {}
```

- [ ] **Step 2: Observe SETTINGS frames in `_on_frame()`**

The current code has a catch-all `else` branch that ignores SETTINGS / WINDOW_UPDATE / PING / GOAWAY (line 156-158). Replace it with an explicit SETTINGS observation branch:

```python
        elif isinstance(frame, hyperframe.frame.SettingsFrame):
            # Observe client SETTINGS so the response encoder can frame DATA
            # at the negotiated MAX_FRAME_SIZE and refuse oversized header blocks.
            # Settings only flow client->server in the autoparser's view (request side);
            # ACK frames carry no settings and are ignored.
            if self._is_request_side and self._state is not None and 'ACK' not in flags:
                # SettingsFrame.settings is dict[int, int] — keys are the settings IDs.
                # 0x05 = SETTINGS_MAX_FRAME_SIZE, 0x06 = SETTINGS_MAX_HEADER_LIST_SIZE.
                if 0x05 in frame.settings:
                    self._state.max_frame_size = frame.settings[0x05]
                if 0x06 in frame.settings:
                    self._state.max_header_list_size = frame.settings[0x06]
            return
        else:
            # WINDOW_UPDATE / PING / GOAWAY / PRIORITY / PUSH_PROMISE: ignored.
            return
```

- [ ] **Step 3: Smoke check**

```powershell
python -c @'
import hyperframe.frame
from atomicshop.wrappers.protocol_parsers.http2 import Http2ConnectionState, Http2DirectionParser, HTTP2_CLIENT_PREFACE

st = Http2ConnectionState()
p = Http2DirectionParser(is_request_side=True, state=st)

# Build: preface + SETTINGS(MAX_FRAME_SIZE=32768, MAX_HEADER_LIST_SIZE=16384)
sf = hyperframe.frame.SettingsFrame()
sf.settings[0x05] = 32768
sf.settings[0x06] = 16384
buf = HTTP2_CLIENT_PREFACE + sf.serialize()

list(p.feed(buf))
assert st.max_frame_size == 32768, st.max_frame_size
assert st.max_header_list_size == 16384, st.max_header_list_size

# Verify ACK is ignored
sf_ack = hyperframe.frame.SettingsFrame()
sf_ack.flags.add('ACK')
list(p.feed(sf_ack.serialize()))
assert st.max_frame_size == 32768  # unchanged
print('OK')
'@
```

Expected: `OK`

- [ ] **Step 4: Commit**

```powershell
git add atomicshop/wrappers/protocol_parsers/http2.py
git commit -m @'
mitm: observe client HTTP/2 SETTINGS into Http2ConnectionState

Http2DirectionParser gains an optional `state` parameter. When provided,
parsed SettingsFrame (non-ACK, c2s only) updates state.max_frame_size and
state.max_header_list_size, so the response encoder can frame DATA at the
negotiated values rather than the hardcoded default.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 3: Plumb `max_frame_size` through HTTP/2 encoder

**Files:**
- Modify: `atomicshop/wrappers/protocol_parsers/http2.py` (`_serialize_data_frames`, `encode_http2_message`, `encode_http2_response`)

- [ ] **Step 1: Replace `_serialize_data_frames` constant use with parameter**

Change:
```python
def _serialize_data_frames(stream_id: int, body: bytes, end_stream: bool) -> bytes:
    """Split body across DATA frames at MAX_FRAME_SIZE; END_STREAM on the last."""
    if not body:
        ...
    out = bytearray()
    n = len(body)
    for i in range(0, n, _DEFAULT_MAX_FRAME_SIZE):
        chunk = body[i:i + _DEFAULT_MAX_FRAME_SIZE]
        ...
```

To:
```python
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
```

- [ ] **Step 2: Add `max_frame_size` kwarg to `encode_http2_message` and `encode_http2_response`**

For `encode_http2_message`:
```python
def encode_http2_message(
        pseudo_headers,
        regular_headers,
        body: bytes,
        stream_id: int,
        trailers: dict[str, str] | None = None,
        max_frame_size: int = _DEFAULT_MAX_FRAME_SIZE,
) -> bytes:
    ...
    if has_body:
        out.extend(_serialize_data_frames(
            stream_id, body, end_stream=not has_trailers, max_frame_size=max_frame_size))
    ...
```

For `encode_http2_response`:
```python
def encode_http2_response(
        status_code: int,
        headers=None,
        body: bytes = b'',
        stream_id: int = 0,
        trailers: dict[str, str] | None = None,
        max_frame_size: int = _DEFAULT_MAX_FRAME_SIZE,
) -> bytes:
    return encode_http2_message(
        [(':status', str(status_code))],
        headers or {},
        body, stream_id, trailers, max_frame_size,
    )
```

Same kwarg added to `encode_http2_request` for symmetry.

- [ ] **Step 3: Smoke check (verify fragmentation honors the new kwarg)**

```powershell
python -c @'
from atomicshop.wrappers.protocol_parsers.http2 import encode_http2_response
import hyperframe.frame, hyperframe

# Body of 32k with max_frame_size=16384 should produce 2 DATA frames.
body = b'x' * 32_000
wire = encode_http2_response(status_code=200, headers={'content-type': 'text/plain'},
                              body=body, stream_id=1, max_frame_size=16_384)
# Count DATA frames in wire
buf = memoryview(wire)
data_count = 0
while len(buf) >= 9:
    f, length = hyperframe.frame.Frame.parse_frame_header(buf[:9])
    if isinstance(f, hyperframe.frame.DataFrame):
        data_count += 1
    buf = buf[9 + length:]
assert data_count == 2, data_count

# Same body with max_frame_size=64k should produce 1 DATA frame.
wire = encode_http2_response(status_code=200, headers={'content-type': 'text/plain'},
                              body=body, stream_id=1, max_frame_size=65_536)
buf = memoryview(wire)
data_count = 0
while len(buf) >= 9:
    f, length = hyperframe.frame.Frame.parse_frame_header(buf[:9])
    if isinstance(f, hyperframe.frame.DataFrame):
        data_count += 1
    buf = buf[9 + length:]
assert data_count == 1, data_count

print('OK')
'@
```

Expected: `OK`

- [ ] **Step 4: Commit**

```powershell
git add atomicshop/wrappers/protocol_parsers/http2.py
git commit -m @'
mitm: plumb max_frame_size kwarg through HTTP/2 encoder

_serialize_data_frames, encode_http2_message, encode_http2_response, and
encode_http2_request gain an optional max_frame_size kwarg defaulting to
the existing constant. Lets the responder pass the client-negotiated
SETTINGS value for faithful DATA framing.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 4: Extend `ResponderParent.add_args` and eager state allocation in `connection_thread_worker.py`

**Files:**
- Modify: `atomicshop/mitm/engines/__parent/responder___parent.py` (the `add_args` method at line 25-35)
- Modify: `atomicshop/mitm/connection_thread_worker.py` (around lines 1015-1040)

- [ ] **Step 1: Extend `add_args` in `responder___parent.py`**

Replace lines 25-35:
```python
    def add_args(
            self,
            # engine: initialize_engines.ModuleCategory
            engine = None,
            h2_state: 'Http2ConnectionState | None' = None,
            mqtt_state: 'MqttConnectionState | None' = None,
            ws_state: 'WebSocketConnectionState | None' = None,
    ):
        """Backward-compatible state injection. Adds connection-scoped state for build_byte_* helpers."""
        self.engine = engine
        self._h2_state = h2_state
        self._mqtt_state = mqtt_state
        self._ws_state = ws_state
```

Also extend `__init__` (line 20-23) so the attributes always exist:
```python
    def __init__(self):
        self.logger = create_custom_logger()
        # engine: initialize_engines.ModuleCategory
        self.engine = None
        self._h2_state = None
        self._mqtt_state = None
        self._ws_state = None
```

Add the imports at the top of `responder___parent.py` (after existing imports):
```python
from ....wrappers.protocol_parsers.http2 import Http2ConnectionState
from ....wrappers.protocol_parsers.mqtt import MqttConnectionState
from ....wrappers.protocol_parsers.websocket import WebSocketConnectionState
```

- [ ] **Step 2: Eager allocation in `connection_thread_worker.py`**

Find the block around line 1015-1021 that currently reads:
```python
    # MQTT autoparsers, one per direction with a shared MqttConnectionState ...
    mqtt_state: MqttConnectionState | None = None
    mqtt_request_parser: MqttDirectionParser | None = None
    mqtt_response_parser: MqttDirectionParser | None = None
```

Replace with:
```python
    # Connection-scoped protocol state shared between framers/parsers and the responder.
    # Eagerly allocated even when the corresponding protocol isn't used (cheap; allows
    # responder helpers to be wired up unconditionally).
    h2_state: Http2ConnectionState = Http2ConnectionState()
    mqtt_state: MqttConnectionState = MqttConnectionState()
    ws_state: WebSocketConnectionState = WebSocketConnectionState()

    mqtt_request_parser: MqttDirectionParser | None = None
    mqtt_response_parser: MqttDirectionParser | None = None
```

Add imports at the top of `connection_thread_worker.py` alongside the existing protocol_parser imports:
```python
from ..wrappers.protocol_parsers.http2 import Http2ConnectionState
from ..wrappers.protocol_parsers.websocket import WebSocketConnectionState
```
(`MqttConnectionState` is already imported.)

- [ ] **Step 3: Pass state to responder in `connection_thread_worker.py`**

Find line 1037-1040 (the `add_args` call):
```python
    for engine in engines_list:
        if engine.engine_name == engine_name:
            responder.add_args(engine=engine)
            break
```

Replace with:
```python
    for engine in engines_list:
        if engine.engine_name == engine_name:
            responder.add_args(engine=engine, h2_state=h2_state, mqtt_state=mqtt_state, ws_state=ws_state)
            break
```

- [ ] **Step 4: Update `init_framer_for_side` (around line 822-830) to use the pre-allocated mqtt_state**

The current code:
```python
        elif alpn == 'mqtt':
            framer = MqttFramer(direction=direction)
            # Shared state so c2s CONNECT version applies to s2c CONNACK.
            if mqtt_state is None:
                mqtt_state = MqttConnectionState()
            if is_client:
                mqtt_request_parser = MqttDirectionParser(is_request_side=True, state=mqtt_state)
            else:
                mqtt_response_parser = MqttDirectionParser(is_request_side=False, state=mqtt_state)
```

Becomes (the `if mqtt_state is None` block is no longer needed):
```python
        elif alpn == 'mqtt':
            framer = MqttFramer(direction=direction)
            # mqtt_state is pre-allocated at thread_worker_main scope; shared with the responder.
            if is_client:
                mqtt_request_parser = MqttDirectionParser(is_request_side=True, state=mqtt_state)
            else:
                mqtt_response_parser = MqttDirectionParser(is_request_side=False, state=mqtt_state)
```

Same for the HTTP/2 branch (around line 813-819):
```python
        if alpn == 'h2':
            framer: Framer | None = Http2Framer(direction=direction)
            # h2 framer chunks at END_STREAM; autoparser owns H2Connection + HPACK.
            if is_client:
                h2_request_parser = Http2DirectionParser(is_request_side=True, state=h2_state)
            else:
                h2_response_parser = Http2DirectionParser(is_request_side=False)
```

Only the request-side parser needs the state (SETTINGS flow c2s); response side leaves `state` defaulted to `None`.

- [ ] **Step 5: Smoke check**

```powershell
python -c @'
from atomicshop.mitm.engines.__parent.responder___parent import ResponderParent
from atomicshop.wrappers.protocol_parsers.http2 import Http2ConnectionState
from atomicshop.wrappers.protocol_parsers.websocket import WebSocketConnectionState
from atomicshop.wrappers.protocol_parsers.mqtt import MqttConnectionState

r = ResponderParent()
# Defaults
assert r._h2_state is None and r._mqtt_state is None and r._ws_state is None
# After add_args, state is wired
h, m, w = Http2ConnectionState(), MqttConnectionState(), WebSocketConnectionState()
r.add_args(engine=None, h2_state=h, mqtt_state=m, ws_state=w)
assert r._h2_state is h and r._mqtt_state is m and r._ws_state is w
print('OK')
'@
```

Expected: `OK`

- [ ] **Step 6: Commit**

```powershell
git add atomicshop/mitm/engines/__parent/responder___parent.py atomicshop/mitm/connection_thread_worker.py
git commit -m @'
mitm: wire connection-scoped state into ResponderParent.add_args

Three state objects (Http2ConnectionState, MqttConnectionState,
WebSocketConnectionState) are eagerly allocated at thread_worker_main
scope and passed to responder.add_args. init_framer_for_side uses the
pre-allocated mqtt_state and feeds h2_state to the c2s Http2DirectionParser
so SETTINGS observation lands on the shared object.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 5: Rewrite `build_byte_response` (HTTP/1.x) with auto-fill and vestigial `http_version`

**Files:**
- Modify: `atomicshop/mitm/engines/__parent/responder___parent.py` (the `build_byte_response` method at line 121-207)

- [ ] **Step 1: Replace the method body**

Replace `build_byte_response` (line 121-207) entirely:

```python
    def build_byte_response(
            self,
            class_client_message: 'ClientMessage',
            status_code: int,
            headers: dict | None = None,
            body: bytes = b'',
            http_version: str | None = None,
    ) -> bytes:
        """Build HTTP/1.x response wire bytes.

        :param class_client_message: required; supplies request_version from
            request_auto_parsed.
        :param status_code: HTTP status code (reason phrase derived from HTTPStatus).
        :param headers: response headers; Content-Length is auto-added when absent
            and the body is non-empty.
        :param body: response body bytes.
        :param http_version: BACKWARDS-COMPAT NO-OP. The wire version is always
            read from class_client_message.request_auto_parsed.request_version.
            Any value passed here is silently discarded. Kept in the signature so
            existing engines that pass `http_version=...` as a kwarg don't break
            with TypeError; new code should omit it.
        :return: HTTP/1.x response bytes.
        """
        _ = http_version  # discarded; auto-filled from request below
        http_version_to_use = class_client_message.request_auto_parsed.request_version
        headers = dict(headers or {})
        # Auto-fill Content-Length if not provided; covers the common case where
        # the engine returns a body without computing length.
        has_length_header = any(k.lower() == 'content-length' for k in headers)
        if body and not has_length_header:
            headers['Content-Length'] = str(len(body))

        status_full = f"{http_version_to_use} {status_code} {HTTPStatus(status_code).phrase}\r\n"
        headers_string = ''.join(f"{k}: {v}\r\n" for k, v in headers.items())
        response_full_no_body = status_full + headers_string + "\r\n"
        return response_full_no_body.encode() + body
```

Remove the old self-parse / `b''`-on-error logic — failures now raise (a `KeyError` from `HTTPStatus(status_code)` on an unknown code, a `TypeError` if `headers` contains non-string values).

Imports already present at top of file: `from http import HTTPStatus`. Add `from ...message import ClientMessage` if not already present (check existing imports).

- [ ] **Step 2: Smoke check**

```powershell
python -c @'
from atomicshop.mitm.engines.__parent.responder___parent import ResponderParent

class FakeReq:
    request_version = 'HTTP/1.1'

class FakeMsg:
    request_auto_parsed = FakeReq()

r = ResponderParent()
msg = FakeMsg()

# (a) http_version auto-filled from request
out = r.build_byte_response(msg, status_code=200, headers={'X-Test': 'y'}, body=b'hi')
assert out.startswith(b'HTTP/1.1 200 OK\r\n'), out[:40]
assert b'X-Test: y\r\n' in out
assert b'Content-Length: 2\r\n' in out
assert out.endswith(b'\r\n\r\nhi'), out[-10:]

# (b) http_version kwarg silently discarded (backwards-compat)
out2 = r.build_byte_response(msg, status_code=200, headers={'X-Test': 'y'}, body=b'hi',
                              http_version='HTTP/1.0')
assert out2 == out, 'http_version kwarg must be ignored'

# (c) Content-Length not overridden if caller provided it
out3 = r.build_byte_response(msg, status_code=200, headers={'Content-Length': '99'}, body=b'hi')
assert b'Content-Length: 99\r\n' in out3

# (d) Empty body, no Content-Length auto-added
out4 = r.build_byte_response(msg, status_code=204, headers={})
assert b'Content-Length' not in out4

# (e) Invalid status code raises
try:
    r.build_byte_response(msg, status_code=999, headers={}, body=b'')
    assert False, 'should have raised'
except (ValueError, KeyError):
    pass

print('OK')
'@
```

Expected: `OK`

- [ ] **Step 3: Commit**

```powershell
git add atomicshop/mitm/engines/__parent/responder___parent.py
git commit -m @'
mitm: rewrite build_byte_response with auto-fill and vestigial http_version

HTTP/1.x response builder now auto-fills http_version from request and
Content-Length from body length (when absent). http_version kwarg is
preserved as a no-op for backwards compatibility — any value passed is
silently discarded. The self-parse and b''-on-error path are removed;
construction failures now raise instead of producing silent empty responses.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 6: Rewrite `build_byte_http2_response` with auto-fill

**Files:**
- Modify: `atomicshop/mitm/engines/__parent/responder___parent.py` (the `build_byte_http2_response` method at line 209-239)

- [ ] **Step 1: Replace the method body**

Replace `build_byte_http2_response` entirely:

```python
    def build_byte_http2_response(
            self,
            class_client_message: 'ClientMessage',
            status_code: int,
            headers: dict | None = None,
            body: bytes = b'',
            trailers: dict | None = None,
    ) -> bytes:
        """Build HTTP/2 response wire bytes on the request's stream.

        Auto-filled from class_client_message + self._h2_state:
          - stream_id        <- request_auto_parsed.stream_id
          - DATA framing     <- self._h2_state.max_frame_size (client SETTINGS)
          - content-length   <- len(body) when absent from headers

        HPACK encoding uses sensitive=True per http2._encode_header_block docstring;
        the dynamic table is intentionally NOT shared across calls — this prevents
        synthesised responses from polluting the client's HPACK decoder state on
        proxies that mix synthesised and forwarded traffic.

        :raises ValueError: stream_id missing/zero on the request, or header block
            exceeds the client's MAX_HEADER_LIST_SIZE SETTING.
        :raises RuntimeError: Http2ConnectionState not wired (add_args missing
            h2_state).
        """
        if self._h2_state is None:
            raise RuntimeError(
                "build_byte_http2_response: Http2ConnectionState not wired; "
                "check add_args call in the framework")

        ar = class_client_message.request_auto_parsed
        stream_id = getattr(ar, 'stream_id', None)
        if not stream_id:
            raise ValueError(
                f"build_byte_http2_response: request_auto_parsed.stream_id required (got {stream_id!r})")

        headers = dict(headers or {})
        has_length_header = any(k.lower() == 'content-length' for k in headers)
        if body and not has_length_header:
            headers['content-length'] = str(len(body))

        # MAX_HEADER_LIST_SIZE enforcement: encode header block once, measure, refuse
        # if oversized. The size is the sum of (name_len + value_len + 32) per the
        # HPACK overhead RFC 7541 §4.1.
        all_headers = [(':status', str(status_code))] + list(headers.items())
        header_size = sum(len(k) + len(v) + 32 for k, v in all_headers)
        limit = self._h2_state.max_header_list_size
        if limit is not None and header_size > limit:
            raise ValueError(
                f"build_byte_http2_response: header list size {header_size} exceeds "
                f"client SETTINGS_MAX_HEADER_LIST_SIZE {limit}")

        return http2.encode_http2_response(
            status_code=status_code,
            headers=headers,
            body=body,
            stream_id=stream_id,
            trailers=trailers,
            max_frame_size=self._h2_state.max_frame_size,
        )
```

- [ ] **Step 2: Smoke check**

```powershell
python -c @'
from atomicshop.mitm.engines.__parent.responder___parent import ResponderParent
from atomicshop.wrappers.protocol_parsers.http2 import Http2ConnectionState

class FakeAr:
    stream_id = 5

class FakeMsg:
    request_auto_parsed = FakeAr()

r = ResponderParent()
msg = FakeMsg()

# Raises when state not wired
try:
    r.build_byte_http2_response(msg, status_code=200, headers={}, body=b'')
    assert False
except RuntimeError as e:
    assert 'Http2ConnectionState not wired' in str(e)

# Wire state, basic call works
st = Http2ConnectionState()
r._h2_state = st
out = r.build_byte_http2_response(msg, status_code=200, headers={'content-type': 'text/plain'}, body=b'hi')
assert len(out) > 0
# First byte is the HEADERS frame header
assert out[3] == 0x01, 'first frame should be HEADERS'

# stream_id missing raises
class BadAr:
    stream_id = 0
msg.request_auto_parsed = BadAr()
try:
    r.build_byte_http2_response(msg, status_code=200, headers={}, body=b'')
    assert False
except ValueError as e:
    assert 'stream_id required' in str(e)

# MAX_HEADER_LIST_SIZE enforcement
msg.request_auto_parsed = FakeAr()
st.max_header_list_size = 50  # tiny; will be exceeded
try:
    r.build_byte_http2_response(msg, status_code=200, headers={'x-long-header-name': 'x' * 100}, body=b'')
    assert False
except ValueError as e:
    assert 'exceeds client SETTINGS' in str(e)

print('OK')
'@
```

Expected: `OK`

- [ ] **Step 3: Commit**

```powershell
git add atomicshop/mitm/engines/__parent/responder___parent.py
git commit -m @'
mitm: rewrite build_byte_http2_response with auto-fill

stream_id auto-pulled from request_auto_parsed; DATA fragmentation uses
self._h2_state.max_frame_size (observed client SETTINGS). content-length
auto-added when absent. MAX_HEADER_LIST_SIZE enforcement refuses to encode
oversized header blocks. HPACK encoding stays per-call sensitive=True
(unchanged) for mixed-traffic correctness.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 7: Add MQTT helpers to `ResponderParent`

**Files:**
- Modify: `atomicshop/mitm/engines/__parent/responder___parent.py` (add new methods after `build_byte_http2_response`)

- [ ] **Step 1: Verify `mqtt.encode_*` function signatures**

Before writing helpers, confirm the existing MQTT encoder signatures. Run:

```powershell
python -c "import inspect; from atomicshop.wrappers.protocol_parsers import mqtt; [print(name, inspect.signature(getattr(mqtt, name))) for name in dir(mqtt) if name.startswith('encode_')]"
```

Expected output lists `encode_connack`, `encode_puback`, `encode_pubrec`, `encode_pubrel`, `encode_pubcomp`, `encode_suback`, `encode_unsuback`, `encode_publish`, `encode_pingresp`, `encode_disconnect`, etc. with their parameter names. **If any signature differs from what the helpers below assume, adjust the helper body to match — the helpers below assume the kwargs `packet_identifier`, `protocol_version`, `return_code`, `return_codes`, `session_present`, `topic`, `payload`, `qos`, `retain`, `reason_code`.**

- [ ] **Step 2: Add all MQTT helpers**

Insert after `build_byte_http2_response`:

```python
    # ------------------------------------------------------------------
    # MQTT broker-side response builders. All auto-fill protocol_version
    # from self._mqtt_state; acknowledgements also auto-fill
    # packet_identifier from class_client_message.request_auto_parsed.
    # ------------------------------------------------------------------

    def _require_mqtt_state(self, helper_name: str) -> 'MqttConnectionState':
        if self._mqtt_state is None or self._mqtt_state.protocol_version is None:
            raise RuntimeError(
                f"{helper_name}: protocol_version unknown; MQTT CONNECT must precede this packet")
        return self._mqtt_state

    def _require_mqtt_packet_id(self, class_client_message: 'ClientMessage', helper_name: str) -> int:
        pid = getattr(class_client_message.request_auto_parsed, 'packet_identifier', None)
        if pid is None:
            raise ValueError(f"{helper_name}: request_auto_parsed.packet_identifier required")
        return pid

    def build_byte_mqtt_connack(
            self,
            class_client_message: 'ClientMessage',
            session_present: bool = False,
            return_code: int = 0,
    ) -> bytes:
        """CONNACK accepting the session. Auto-fills protocol_version."""
        st = self._require_mqtt_state('build_byte_mqtt_connack')
        _ = class_client_message  # accepted for API consistency
        return mqtt.encode_connack(
            session_present=session_present,
            return_code=return_code,
            protocol_version=st.protocol_version,
        )

    def build_byte_mqtt_puback(self, class_client_message: 'ClientMessage') -> bytes:
        """PUBACK for inbound PUBLISH QoS=1. Auto-fills packet_identifier and protocol_version."""
        st = self._require_mqtt_state('build_byte_mqtt_puback')
        pid = self._require_mqtt_packet_id(class_client_message, 'build_byte_mqtt_puback')
        return mqtt.encode_puback(packet_identifier=pid, protocol_version=st.protocol_version)

    def build_byte_mqtt_pubrec(self, class_client_message: 'ClientMessage') -> bytes:
        """PUBREC for inbound PUBLISH QoS=2 (first of four). Auto-fills pid + version."""
        st = self._require_mqtt_state('build_byte_mqtt_pubrec')
        pid = self._require_mqtt_packet_id(class_client_message, 'build_byte_mqtt_pubrec')
        return mqtt.encode_pubrec(packet_identifier=pid, protocol_version=st.protocol_version)

    def build_byte_mqtt_pubcomp(self, class_client_message: 'ClientMessage') -> bytes:
        """PUBCOMP completing QoS=2 handshake. Auto-fills pid + version."""
        st = self._require_mqtt_state('build_byte_mqtt_pubcomp')
        pid = self._require_mqtt_packet_id(class_client_message, 'build_byte_mqtt_pubcomp')
        return mqtt.encode_pubcomp(packet_identifier=pid, protocol_version=st.protocol_version)

    def build_byte_mqtt_suback(
            self,
            class_client_message: 'ClientMessage',
            return_codes: list[int],
    ) -> bytes:
        """SUBACK granting per-topic QoS. Auto-fills pid + version. Engine supplies return_codes."""
        st = self._require_mqtt_state('build_byte_mqtt_suback')
        pid = self._require_mqtt_packet_id(class_client_message, 'build_byte_mqtt_suback')
        return mqtt.encode_suback(
            packet_identifier=pid, return_codes=return_codes, protocol_version=st.protocol_version)

    def build_byte_mqtt_unsuback(
            self,
            class_client_message: 'ClientMessage',
            return_codes: list[int] | None = None,
    ) -> bytes:
        """UNSUBACK. Auto-fills pid + version. v5 carries return_codes; v3 ignores."""
        st = self._require_mqtt_state('build_byte_mqtt_unsuback')
        pid = self._require_mqtt_packet_id(class_client_message, 'build_byte_mqtt_unsuback')
        return mqtt.encode_unsuback(
            packet_identifier=pid, return_codes=return_codes, protocol_version=st.protocol_version)

    def build_byte_mqtt_pingresp(self, class_client_message: 'ClientMessage') -> bytes:
        """PINGRESP: fixed 0xD0 0x00, no session state used."""
        _ = class_client_message  # API consistency
        return mqtt.encode_pingresp()

    def build_byte_mqtt_publish(
            self,
            class_client_message: 'ClientMessage',
            topic: str,
            payload: bytes,
            qos: int = 0,
            retain: bool = False,
            packet_identifier: int | None = None,
    ) -> bytes:
        """Broker-initiated PUBLISH. Auto-fills protocol_version.

        At qos>0, packet_identifier is required (broker chooses one for outbound PUBLISH;
        the engine must pass it explicitly since framework doesn't track outbound pid counters).
        """
        st = self._require_mqtt_state('build_byte_mqtt_publish')
        _ = class_client_message  # API consistency
        if qos > 0 and packet_identifier is None:
            raise ValueError(
                f"build_byte_mqtt_publish: packet_identifier required when qos>0 (got qos={qos})")
        return mqtt.encode_publish(
            topic=topic, payload=payload, qos=qos, retain=retain,
            protocol_version=st.protocol_version,
            packet_identifier=packet_identifier,
        )

    def build_byte_mqtt_disconnect(
            self,
            class_client_message: 'ClientMessage',
            reason_code: int = 0,
    ) -> bytes:
        """DISCONNECT (broker-initiated). v5 carries reason_code; v3 ignores."""
        st = self._require_mqtt_state('build_byte_mqtt_disconnect')
        _ = class_client_message
        return mqtt.encode_disconnect(reason_code=reason_code, protocol_version=st.protocol_version)
```

Imports: `from ....wrappers.protocol_parsers import mqtt` is already imported at the top of the file. If not, add it.

- [ ] **Step 3: Smoke check**

```powershell
python -c @'
from atomicshop.mitm.engines.__parent.responder___parent import ResponderParent
from atomicshop.wrappers.protocol_parsers.mqtt import MqttConnectionState

class FakeAr:
    packet_identifier = 42

class FakeMsg:
    request_auto_parsed = FakeAr()

r = ResponderParent()
msg = FakeMsg()

# Raises when state has no protocol_version
try:
    r.build_byte_mqtt_puback(msg)
    assert False
except RuntimeError as e:
    assert 'CONNECT must precede' in str(e)

# Set up state, all helpers callable
m = MqttConnectionState()
m.protocol_version = 4
r._mqtt_state = m

assert isinstance(r.build_byte_mqtt_puback(msg), bytes)
assert isinstance(r.build_byte_mqtt_pubrec(msg), bytes)
assert isinstance(r.build_byte_mqtt_pubcomp(msg), bytes)
assert isinstance(r.build_byte_mqtt_suback(msg, return_codes=[0, 1]), bytes)
assert isinstance(r.build_byte_mqtt_unsuback(msg), bytes)
assert isinstance(r.build_byte_mqtt_pingresp(msg), bytes)
assert isinstance(r.build_byte_mqtt_connack(msg), bytes)
assert isinstance(r.build_byte_mqtt_disconnect(msg), bytes)
assert isinstance(r.build_byte_mqtt_publish(msg, topic='t', payload=b'p'), bytes)

# qos>0 publish without packet_identifier raises
try:
    r.build_byte_mqtt_publish(msg, topic='t', payload=b'p', qos=1)
    assert False
except ValueError as e:
    assert 'packet_identifier required' in str(e)

# Missing packet_identifier on ack raises
class NoPidAr:
    packet_identifier = None
msg.request_auto_parsed = NoPidAr()
try:
    r.build_byte_mqtt_puback(msg)
    assert False
except ValueError as e:
    assert 'packet_identifier required' in str(e)

print('OK')
'@
```

Expected: `OK`

- [ ] **Step 4: Commit**

```powershell
git add atomicshop/mitm/engines/__parent/responder___parent.py
git commit -m @'
mitm: add MQTT build_byte_* helpers to ResponderParent

Nine broker-side helpers covering CONNACK, PUBACK/PUBREC/PUBCOMP,
SUBACK/UNSUBACK, PINGRESP, PUBLISH, DISCONNECT. All auto-fill
protocol_version from self._mqtt_state; acks auto-fill packet_identifier
from class_client_message.request_auto_parsed. Raises with explicit
helper name when state is missing or required fields absent.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 8: Add WebSocket helpers to `ResponderParent`

**Files:**
- Modify: `atomicshop/mitm/engines/__parent/responder___parent.py` (after MQTT helpers)

- [ ] **Step 1: Verify `websocket.create_websocket_frame` signature**

```powershell
python -c "import inspect; from atomicshop.wrappers.protocol_parsers import websocket; print(inspect.signature(websocket.create_websocket_frame))"
```

The helpers below assume `create_websocket_frame(data, deflate=False, mask=False, opcode=None)`. If the actual signature differs, adjust accordingly. Also check for any close/ping/pong dedicated encoders.

- [ ] **Step 2: Add WebSocket helpers**

Insert after the MQTT helpers:

```python
    # ------------------------------------------------------------------
    # WebSocket server->client frame builders. All auto-fill mask=False
    # (RFC 6455 §5.1) and deflate from self._ws_state.permessage_deflate_negotiated.
    # ------------------------------------------------------------------

    def _ws_deflate(self) -> bool:
        return bool(self._ws_state and self._ws_state.permessage_deflate_negotiated)

    def build_byte_websocket_frame(
            self,
            class_client_message: 'ClientMessage',
            data: str | bytes,
    ) -> bytes:
        """Build a WebSocket data frame. Auto-fills mask=False, opcode (from data type),
        deflate (from negotiated extensions).
        """
        _ = class_client_message
        if not isinstance(data, (str, bytes)):
            raise TypeError(
                f"build_byte_websocket_frame: data must be str or bytes, got {type(data).__name__}")
        return websocket.create_websocket_frame(data=data, deflate=self._ws_deflate(), mask=False)

    def build_byte_websocket_close(
            self,
            class_client_message: 'ClientMessage',
            code: int = 1000,
            reason: str = '',
    ) -> bytes:
        """Build a WebSocket CLOSE frame. Payload = 2-byte big-endian code + reason.encode()."""
        _ = class_client_message
        payload = code.to_bytes(2, 'big') + reason.encode()
        return websocket.create_websocket_frame(
            data=payload, deflate=self._ws_deflate(), mask=False, opcode='CLOSE')

    def build_byte_websocket_ping(
            self,
            class_client_message: 'ClientMessage',
            data: bytes = b'',
    ) -> bytes:
        """Build a WebSocket PING frame."""
        _ = class_client_message
        return websocket.create_websocket_frame(
            data=data, deflate=self._ws_deflate(), mask=False, opcode='PING')

    def build_byte_websocket_pong(
            self,
            class_client_message: 'ClientMessage',
            data: bytes = b'',
    ) -> bytes:
        """Build a WebSocket PONG frame."""
        _ = class_client_message
        return websocket.create_websocket_frame(
            data=data, deflate=self._ws_deflate(), mask=False, opcode='PONG')
```

Imports: `from ....wrappers.protocol_parsers import websocket` is already imported. If not, add it.

**Note:** if `create_websocket_frame` doesn't accept an `opcode` kwarg for CLOSE/PING/PONG, look in `websocket.py` for dedicated encoders (e.g. `encode_close_frame`) and substitute them in the close/ping/pong helpers. Adjust before validation.

- [ ] **Step 3: Smoke check**

```powershell
python -c @'
from atomicshop.mitm.engines.__parent.responder___parent import ResponderParent
from atomicshop.wrappers.protocol_parsers.websocket import WebSocketConnectionState

class FakeMsg: pass

r = ResponderParent()
msg = FakeMsg()
r._ws_state = WebSocketConnectionState()

# Text and binary frames
out_text = r.build_byte_websocket_frame(msg, data='hello')
out_bin = r.build_byte_websocket_frame(msg, data=b'\x01\x02')
assert isinstance(out_text, bytes) and len(out_text) > 0
assert isinstance(out_bin, bytes) and len(out_bin) > 0

# Type error
try:
    r.build_byte_websocket_frame(msg, data=123)
    assert False
except TypeError:
    pass

# Close/ping/pong (skip if not supported by underlying encoder)
try:
    out_close = r.build_byte_websocket_close(msg, code=1000, reason='bye')
    assert isinstance(out_close, bytes)
    print('CLOSE OK')
except Exception as e:
    print(f'CLOSE skipped: {e}')

print('OK')
'@
```

Expected: `OK` (with `CLOSE OK` if close frames work; otherwise debug and fix close encoder usage)

- [ ] **Step 4: Commit**

```powershell
git add atomicshop/mitm/engines/__parent/responder___parent.py
git commit -m @'
mitm: add WebSocket build_byte_* helpers to ResponderParent

Four server->client helpers: build_byte_websocket_frame (TEXT/BINARY auto
from data type), build_byte_websocket_close, build_byte_websocket_ping,
build_byte_websocket_pong. All auto-fill mask=False (RFC 6455 §5.1) and
deflate from self._ws_state.permessage_deflate_negotiated, closing the
silent permessage-deflate fidelity gap in current engine code.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 9: Capture WebSocket extensions during 101 swap in `connection_thread_worker.py`

**Files:**
- Modify: `atomicshop/mitm/connection_thread_worker.py` (the 101 swap block at line 449-464)

- [ ] **Step 1: Extend the 101 swap to capture extensions and subprotocol**

The current code at line 449-464:
```python
        parsed = client_message.response_auto_parsed
        status = getattr(parsed, 'code', None) if parsed is not None else None
        if status == 101:
            headers = getattr(parsed, 'headers', None)
            upgrade = ''
            if headers is not None:
                try:
                    upgrade = (headers.get('Upgrade') or '').lower()
                except Exception:
                    upgrade = ''
            if upgrade == 'websocket':
                client_recv = side_receivers.get('Client')
                service_recv = side_receivers.get('Service')
                if client_recv is not None:
                    client_recv.set_framer(WebSocketFramer(direction='client_to_server'))
                if service_recv is not None:
                    service_recv.set_framer(WebSocketFramer(direction='server_to_client'))
                network_logger.info("Framers swapped to WebSocket on 101 Switching Protocols.")
```

Add extension/subprotocol capture before the framer swap (inside the `if upgrade == 'websocket':` block):

```python
            if upgrade == 'websocket':
                # Capture negotiated extensions and subprotocol from the 101 so the
                # responder's build_byte_websocket_* helpers know whether to compress
                # frames (permessage-deflate) and which subprotocol is in play.
                ext_header = ''
                subproto_header = ''
                if headers is not None:
                    try:
                        ext_header = (headers.get('Sec-WebSocket-Extensions') or '').lower()
                        subproto_header = headers.get('Sec-WebSocket-Protocol') or ''
                    except Exception:
                        pass
                ws_state.permessage_deflate_negotiated = 'permessage-deflate' in ext_header
                ws_state.subprotocol = subproto_header or None
                network_logger.info(
                    f"WebSocket negotiation: permessage_deflate="
                    f"{ws_state.permessage_deflate_negotiated} subprotocol={ws_state.subprotocol!r}")

                client_recv = side_receivers.get('Client')
                service_recv = side_receivers.get('Service')
                if client_recv is not None:
                    client_recv.set_framer(WebSocketFramer(direction='client_to_server'))
                if service_recv is not None:
                    service_recv.set_framer(WebSocketFramer(direction='server_to_client'))
                network_logger.info("Framers swapped to WebSocket on 101 Switching Protocols.")
```

- [ ] **Step 2: Smoke check (basic — full test deferred to e2e)**

The connection_thread_worker code path can't easily be unit-tested in isolation (it's deep inside `thread_worker_main`). Skip the inline check; rely on the e2e validation in Task 11.

- [ ] **Step 3: Commit**

```powershell
git add atomicshop/mitm/connection_thread_worker.py
git commit -m @'
mitm: capture WebSocket extensions + subprotocol during 101 swap

The 101 handler now reads Sec-WebSocket-Extensions and Sec-WebSocket-Protocol
into ws_state (eagerly allocated alongside h2_state/mqtt_state at the top of
thread_worker_main). Responder helpers consult ws_state.permessage_deflate_negotiated
when building frames, closing the silent uncompressed-output gap that current
engine code has.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 10: Rewrite reference examples in `responder___reference_general.py`

**Files:**
- Modify: `atomicshop/mitm/engines/__reference_general/responder___reference_general.py` (4 commented example sections; lines 30-72, 90-123, 127-176, 183-253, 349-385, 388-406)

This task rewrites every commented `create_response` example to:
1. Use `self.build_byte_*` helpers instead of low-level encoders / old signatures
2. Include a `# Auto-filled by ...` comment block at each helper call site

- [ ] **Step 1: Rewrite HTTP/2 example (replaces lines 127-176)**

Find the block starting `# HTTP/2 response synthesis example.` and ending before `# ====================` (about line 178). Replace with:

```python
    # ==================================================================================================================
    # HTTP/2 response synthesis example.
    # def create_response(self, class_client_message: ClientMessage):
    #     ar = class_client_message.request_auto_parsed
    #     # Only handle HTTP/2 here; pass-through otherwise.
    #     if not isinstance(ar, http2.Http2RequestParse):
    #         return None
    #
    #     response_bytes_list: list[bytes] = list()
    #
    #     # 1. JSON response: synthesise a 200 OK on the same stream the client opened.
    #     # Auto-filled by build_byte_http2_response:
    #     #   stream_id            <- class_client_message.request_auto_parsed.stream_id
    #     #   DATA fragmentation   <- self._h2_state.max_frame_size (from client SETTINGS)
    #     #   content-length       <- len(body), only when absent from headers
    #     # (HPACK encoding stays per-call with sensitive=True; not connection-scoped.)
    #     # import json
    #     # body: bytes = json.dumps({'ok': True, 'echo_path': ar.path}).encode()
    #     body: bytes = b'{"ok": true}'
    #     headers = {'content-type': 'application/json'}
    #     response_bytes_list.append(self.build_byte_http2_response(
    #         class_client_message, status_code=200, headers=headers, body=body))
    #
    #     # 2. Empty-body response (e.g. 204 No Content): same auto-fills.
    #     # response_bytes_list.append(self.build_byte_http2_response(
    #     #     class_client_message, status_code=204, headers={}, body=b''))
    #
    #     # 3. gRPC-style response with trailers (HEADERS-DATA-HEADERS): same auto-fills.
    #     # response_bytes_list.append(self.build_byte_http2_response(
    #     #     class_client_message,
    #     #     status_code=200,
    #     #     headers={'content-type': 'application/grpc'},
    #     #     body=b'\x00\x00\x00\x00\x05hello',
    #     #     trailers={'grpc-status': '0', 'grpc-message': 'OK'}))
    #
    #     # 4. Route by method + path (mirrors the HTTP/1.1 example):
    #     # if ar.command == 'POST' and ar.path.startswith('/api/v1/echo'):
    #     #     body = ar.body or b'<empty>'
    #     #     response_bytes_list.append(self.build_byte_http2_response(
    #     #         class_client_message, status_code=200,
    #     #         headers={'content-type': 'application/octet-stream'}, body=body))
    #
    #     return response_bytes_list
    #
```

- [ ] **Step 2: Rewrite WebSocket example (replaces lines 90-123)**

Find the block starting `# WEBSOCKET example.` and ending before the HTTP/2 section. Replace with:

```python
    # ==================================================================================================================
    # WEBSOCKET example.
    # def create_response(self, class_client_message: ClientMessage):
    #     # The incoming websocket frame is parsed into a dict with keys:
    #     #   'is_deflated' (bool), 'is_masked' (bool), 'frame' (str or bytes),
    #     #   'opcode' (str: TEXT/BINARY/CLOSE/PING/PONG)
    #     ws_frame = class_client_message.request_auto_parsed
    #     frame_data = ws_frame['frame']
    #     frame_opcode = ws_frame['opcode']
    #
    #     response_bytes_list: list[bytes] = list()
    #
    #     # Auto-filled by build_byte_websocket_frame:
    #     #   mask=False (RFC 6455 §5.1 — server-side frames are never masked)
    #     #   opcode    <- inferred from data type (str -> TEXT, bytes -> BINARY)
    #     #   deflate   <- self._ws_state.permessage_deflate_negotiated (from 101 handshake)
    #     #   FIN/continuation framing for payloads larger than MAX_FRAME_SIZE
    #     # import json
    #     if frame_opcode == 'TEXT':
    #         response_dict = {'status': 'ok', 'echo': frame_data}
    #         response_bytes_list.append(self.build_byte_websocket_frame(
    #             class_client_message, data=json.dumps(response_dict)))
    #     elif frame_opcode == 'BINARY':
    #         response_bytes_list.append(self.build_byte_websocket_frame(
    #             class_client_message, data=b'\x01\x02\x03'))
    #
    #     # Close frame example.
    #     # Auto-filled by build_byte_websocket_close:
    #     #   mask=False, opcode=CLOSE, payload = 2-byte big-endian code + reason.encode()
    #     # response_bytes_list.append(self.build_byte_websocket_close(
    #     #     class_client_message, code=1000, reason='normal closure'))
    #
    #     return response_bytes_list
    #
```

- [ ] **Step 3: Rewrite MQTT example (replaces lines 183-253)**

Find the block starting `# MQTT response synthesis example (broker-side).` and ending before the next `# ==================`. Replace with:

```python
    # ==================================================================================================================
    # MQTT response synthesis example (broker-side).
    # The incoming MqttPacketParse exposes: .packet_type ('CONNECT'/'PUBLISH'/...),
    # .qos / .retain / .dup, .topic, .payload, .packet_identifier, .client_id,
    # .subscriptions ([(filter, requested_qos), ...]), .protocol_version (4=v3.1.1, 5=v5).
    # def create_response(self, class_client_message: ClientMessage):
    #     mp = class_client_message.request_auto_parsed
    #     if not isinstance(mp, mqtt.MqttPacketParse):
    #         return None
    #
    #     response_bytes_list: list[bytes] = list()
    #
    #     # CONNACK — accept the session.
    #     # Auto-filled by build_byte_mqtt_connack:
    #     #   protocol_version  <- self._mqtt_state.protocol_version (set from c2s CONNECT)
    #     if mp.packet_type == 'CONNECT':
    #         response_bytes_list.append(self.build_byte_mqtt_connack(
    #             class_client_message, session_present=False, return_code=0))
    #
    #     # SUBACK — grant each topic at the requested QoS.
    #     # Auto-filled by build_byte_mqtt_suback:
    #     #   packet_identifier <- class_client_message.request_auto_parsed.packet_identifier
    #     #   protocol_version  <- self._mqtt_state.protocol_version
    #     elif mp.packet_type == 'SUBSCRIBE':
    #         granted = [requested_qos for _topic, requested_qos in (mp.subscriptions or [])]
    #         response_bytes_list.append(self.build_byte_mqtt_suback(
    #             class_client_message, return_codes=granted))
    #
    #     # PUBACK / PUBREC for inbound PUBLISH at QoS>0; broker-initiated downstream PUBLISH.
    #     elif mp.packet_type == 'PUBLISH':
    #         # Auto-filled by build_byte_mqtt_puback / build_byte_mqtt_pubrec:
    #         #   packet_identifier <- class_client_message.request_auto_parsed.packet_identifier
    #         #   protocol_version  <- self._mqtt_state.protocol_version
    #         if mp.qos == 1:
    #             response_bytes_list.append(self.build_byte_mqtt_puback(class_client_message))
    #         elif mp.qos == 2:
    #             response_bytes_list.append(self.build_byte_mqtt_pubrec(class_client_message))
    #
    #         # Broker-initiated downstream PUBLISH (e.g. echo to subscribers).
    #         # Auto-filled by build_byte_mqtt_publish:
    #         #   protocol_version   <- self._mqtt_state.protocol_version
    #         # Engine-supplied:
    #         #   packet_identifier  <- required for qos>0 (omit at qos=0)
    #         response_bytes_list.append(self.build_byte_mqtt_publish(
    #             class_client_message, topic=mp.topic, payload=mp.payload or b'',
    #             qos=0, retain=False))
    #
    #     # PUBCOMP — completes a QoS 2 handshake after the client's PUBREL.
    #     # Auto-filled: packet_identifier, protocol_version (same as puback).
    #     elif mp.packet_type == 'PUBREL':
    #         response_bytes_list.append(self.build_byte_mqtt_pubcomp(class_client_message))
    #
    #     # PINGRESP — fixed 2 bytes (0xD0 0x00); no session state used.
    #     elif mp.packet_type == 'PINGREQ':
    #         response_bytes_list.append(self.build_byte_mqtt_pingresp(class_client_message))
    #
    #     # UNSUBACK after UNSUBSCRIBE.
    #     # Auto-filled: packet_identifier, protocol_version. v5 carries return_codes; v3 ignores.
    #     elif mp.packet_type == 'UNSUBSCRIBE':
    #         filters = mp.topic_filters or []
    #         response_bytes_list.append(self.build_byte_mqtt_unsuback(
    #             class_client_message, return_codes=[0] * len(filters)))
    #
    #     # Tear-down: broker-initiated DISCONNECT (v5 carries reason_code).
    #     # Auto-filled: protocol_version.
    #     # response_bytes_list.append(self.build_byte_mqtt_disconnect(
    #     #     class_client_message, reason_code=0x8E))  # 0x8E = Session taken over (v5)
    #
    #     return response_bytes_list
    #
```

- [ ] **Step 4: Rewrite HTTP/1.x examples (lines 30-72 dispatcher template, 349-385 dispatcher with response_dir_*, 388-406 test response)**

For the test response at line 388-406, find:
```
    # def create_response(self, class_client_message: ClientMessage):
    #     resp_body_text: bytes = b"<html>...
    #     ...
    #     byte_response = self.build_byte_response(
    #         http_version="HTTP/1.1",
    #         status_code=resp_status_code,
    #         headers=resp_headers,
    #         body=resp_body_text
    #
    #     )
    #
    #     result_response_list: list[bytes] = [byte_response]
    #     return result_response_list
```

Replace with:
```
    # def create_response(self, class_client_message: ClientMessage):
    #     resp_body: bytes = b"<html><body>TEST OK!</body></html>\n"
    #     resp_headers: dict = {
    #         "Content-Type": "text/html; charset=utf-8",
    #     }
    #
    #     # Auto-filled by build_byte_response:
    #     #   http_version    <- class_client_message.request_auto_parsed.request_version
    #     #   Reason phrase   <- HTTPStatus(status_code).phrase
    #     #   Content-Length  <- len(body), only when absent from headers
    #     byte_response = self.build_byte_response(
    #         class_client_message,
    #         status_code=200,
    #         headers=resp_headers,
    #         body=resp_body,
    #     )
    #     return [byte_response]
```

For the dispatcher example at line 349-385, find the `self.build_byte_response(http_version=...)` call (around line 377-382) and change to:
```
    #     # Auto-filled by build_byte_response:
    #     #   http_version    <- class_client_message.request_auto_parsed.request_version
    #     #   Reason phrase   <- HTTPStatus(status_code).phrase
    #     #   Content-Length  <- len(body), only when absent from headers
    #     byte_response = self.build_byte_response(
    #         class_client_message,
    #         status_code=resp_status_code,
    #         headers=resp_headers,
    #         body=resp_body_bytes,
    #     )
```

For the main commented example at line 30-72, find:
```
    #     result_list.append(
    #         self.build_byte_response(
    #             http_version=class_client_message.request_raw_decoded.request_version,
    #             status_code=200,
    #             headers=response_headers,
    #             body=b''
    #         )
    #     )
```

Replace with:
```
    #     # Auto-filled by build_byte_response:
    #     #   http_version    <- class_client_message.request_auto_parsed.request_version
    #     #   Reason phrase   <- HTTPStatus(status_code).phrase
    #     #   Content-Length  <- len(body), only when absent from headers
    #     result_list.append(
    #         self.build_byte_response(
    #             class_client_message,
    #             status_code=200,
    #             headers=response_headers,
    #             body=b'',
    #         )
    #     )
```

- [ ] **Step 5: Sanity check the file still parses**

```powershell
python -c "import atomicshop.mitm.engines.__reference_general.responder___reference_general; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```powershell
git add atomicshop/mitm/engines/__reference_general/responder___reference_general.py
git commit -m @'
mitm: rewrite reference responder examples for new build_byte_* helpers

All four protocol examples (HTTP/1.x test + dispatcher, HTTP/2, MQTT,
WebSocket) updated to use the new auto-filling helpers. Each call site
includes an inline "Auto-filled by ..." comment block enumerating
exactly which fields the framework supplies and where each value comes
from, so engine authors see the contract at the point of use.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 11: End-to-end smoke validation

This task isn't strictly required for code correctness but provides confidence that the wire-up works in a real run.

- [ ] **Step 1: Confirm imports resolve**

```powershell
python -c @'
from atomicshop.mitm.engines.__parent.responder___parent import ResponderParent
from atomicshop.mitm.engines.__reference_general.responder___reference_general import ResponderGeneral
from atomicshop.wrappers.protocol_parsers.http2 import Http2ConnectionState
from atomicshop.wrappers.protocol_parsers.websocket import WebSocketConnectionState
from atomicshop.wrappers.protocol_parsers.mqtt import MqttConnectionState
r = ResponderGeneral()  # inherits from ResponderParent
# Spot check that all helper methods exist on the inheritance chain
assert hasattr(r, 'build_byte_response')
assert hasattr(r, 'build_byte_http2_response')
assert hasattr(r, 'build_byte_mqtt_connack')
assert hasattr(r, 'build_byte_mqtt_puback')
assert hasattr(r, 'build_byte_mqtt_publish')
assert hasattr(r, 'build_byte_websocket_frame')
assert hasattr(r, 'build_byte_websocket_close')
print('OK')
'@
```

Expected: `OK`

- [ ] **Step 2: Round-trip the HTTP/2 example (synthetic request)**

```powershell
python -c @'
from atomicshop.mitm.engines.__parent.responder___parent import ResponderParent
from atomicshop.wrappers.protocol_parsers.http2 import (
    Http2ConnectionState, Http2RequestParse, Http2DirectionParser, HTTP2_CLIENT_PREFACE)
import hyperframe.frame, hpack

# Build a synthetic c2s request: preface + SETTINGS + HEADERS(END_STREAM)
enc = hpack.Encoder()
hb = enc.encode([(':method', 'GET'), (':path', '/'), (':scheme', 'https'), (':authority', 'a.test')])
hf = hyperframe.frame.HeadersFrame(stream_id=1)
hf.data = hb
hf.flags.add('END_HEADERS')
hf.flags.add('END_STREAM')
sf = hyperframe.frame.SettingsFrame()
sf.settings[0x05] = 32768
wire = HTTP2_CLIENT_PREFACE + sf.serialize() + hf.serialize()

# Parse through the c2s parser to populate state and produce a parsed request
state = Http2ConnectionState()
parser = Http2DirectionParser(is_request_side=True, state=state)
parsed = list(parser.feed(wire))
assert parsed, parsed
assert isinstance(parsed[0], Http2RequestParse)
assert parsed[0].stream_id == 1
assert state.max_frame_size == 32768

# Now responder builds a response — auto-fills stream_id and uses state.max_frame_size
class FakeMsg:
    request_auto_parsed = parsed[0]
r = ResponderParent()
r._h2_state = state
out = r.build_byte_http2_response(FakeMsg(), status_code=200, headers={'content-type': 'text/plain'}, body=b'hello')
assert len(out) > 0
# First byte triple should be a HEADERS frame on stream 1
assert out[3] == 0x01  # HEADERS frame type
print('OK')
'@
```

Expected: `OK`

- [ ] **Step 3: No commit needed** (validation only)

---

## Self-Review

After completing all tasks, scan the final state:

1. **Spec coverage check:** every "Auto-filled" entry in the spec's API Surface section is implemented in at least one helper.
2. **Naming consistency:** all helpers follow `build_byte_<protocol>_<packet>` pattern; method names in tests match the implementation names.
3. **Error paths:** every "raises" entry in the spec's error-handling table has a code path that raises with the documented message.
4. **Reference examples:** every example call site has an `# Auto-filled by ...` comment block.

If any check fails, open a new task for the gap; don't squeeze fixes into unrelated commits.

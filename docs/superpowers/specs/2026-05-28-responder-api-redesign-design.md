# Responder API Redesign — Auto-Filled Session-Derived Parameters

**Date:** 2026-05-28
**Status:** Approved (brainstorm), pending implementation
**Affects:** `atomicshop.mitm.engines.__parent.responder___parent`, `atomicshop.mitm.engines.__reference_general.responder___reference_general`, `atomicshop.mitm.connection_thread_worker`, `atomicshop.wrappers.protocol_parsers.{http2,websocket,mqtt}`

## Summary

Engine authors currently write session-derived fields (HTTP/2 `stream_id`, MQTT `packet_identifier`, MQTT `protocol_version`, WebSocket `mask`, etc.) by hand in every `create_response`. This redesign moves those fields to auto-fill inside per-protocol `build_byte_*` helpers on `ResponderParent`. Engines stop carrying boilerplate; one real correctness bug (silent WebSocket `permessage-deflate` skip) closes by construction.

## Motivation

Three problems with the current responder surface:

1. **Boilerplate.** Every HTTP/2 response synthesis writes `stream_id=class_client_message.request_auto_parsed.stream_id`. Every MQTT broker reply writes `protocol_version=v, packet_identifier=mp.packet_identifier`. The framework already has these values; repeating them at every call site is friction without value.
2. **Silent fidelity drift.** Today's WebSocket example writes `deflate=False` regardless of whether `permessage-deflate` was negotiated during the 101 handshake. A connection with negotiated compression silently receives uncompressed frames from the proxy. This is invisible to the engine author and to anyone reading the engine code.
3. **Hardcoded `MAX_FRAME_SIZE`.** `wrappers/protocol_parsers/http2.py:_serialize_data_frames` fragments DATA frames at the SETTINGS default (16384). If the client advertised a larger `SETTINGS_MAX_FRAME_SIZE`, the proxy still chops at 16384 — correct but not faithful. Observing the client's SETTINGS lets the proxy send fewer, larger frames when permitted.

   **(Note on HPACK):** `_encode_header_block` already correctly uses `hpack.Encoder` per-call with every header flagged `sensitive=True`. This is deliberate — see the docstring at `http2.py:193-200`: a connection-scoped encoder with a real dynamic table would pollute the client's decoder state on proxies that mix synthesised and forwarded responses. **This design preserves that behavior unchanged.** No connection-scoped HPACK state.

## Goals

- Auto-fill session-derived parameters for all four supported protocols (HTTP/1.x, HTTP/2, MQTT, WebSocket) from connection-scoped state held on `ResponderParent`.
- Surface auto-fill behavior at every reference-example call site so engine authors see the contract at the point of use.
- Replace silent `b''` returns on encoding failure with raised exceptions that the framework's existing error path records.
- Capture WebSocket extension and subprotocol negotiation during the 101 swap so `permessage-deflate` works end-to-end without engine intervention.

## Non-Goals

- **Post-emission validation gate.** Catching wire-invalid bytes that engines or encoders produce, recording them in `statistics.csv` and CRITICAL logs, and blocking the send — that is the subject of a separate follow-up spec. This spec makes correct output the easy path; the gate is a back-end safety net.
- **Full HTTP/2 flow control or stream priority.** Out of scope for a passive MITM observer; the `hyperframe`+`hpack` choice (see `http2.py:8-15`) explicitly rules them out.
- **MQTT v5 properties.** The auto-fill targets are `protocol_version` and `packet_identifier`. Property-list synthesis for v5 stays as engine code.

## Architecture

Three layers, all already partially present:

```
┌─────────────────────────────────────────────────────────────────┐
│ Engine code (responder_<engine_name>.py inheriting              │
│ ResponderParent)                                                │
│                                                                 │
│   def create_response(self, class_client_message):              │
│       return [self.build_byte_http2_response(                   │
│           class_client_message, status_code=200,                │
│           headers={...}, body=b'...')]                          │
└──────────────────────┬──────────────────────────────────────────┘
                       │ self.build_byte_*(class_client_message, ...)
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ ResponderParent (base class)                                    │
│                                                                 │
│  - One instance per connection (created at                      │
│    connection_thread_worker.py:1032).                           │
│  - Hosts build_byte_* helpers for all four protocols.           │
│  - Holds connection-scoped state on self:                       │
│      self._h2_state, self._mqtt_state, self._ws_state.          │
│  - Each helper pulls session-derived fields from                │
│    class_client_message.request_auto_parsed + self._*_state,    │
│    then delegates to the protocol encoder.                      │
└──────────────────────┬──────────────────────────────────────────┘
                       │ encode_http2_response / encode_puback /
                       │ create_websocket_frame / ...
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ wrappers/protocol_parsers/{http,http2,mqtt,websocket}.py        │
│                                                                 │
│  Existing encoder functions. Signatures stay byte-oriented      │
│  (take all params, return bytes). They become a private wire    │
│  layer that engine code no longer calls directly.               │
└─────────────────────────────────────────────────────────────────┘
```

### Connection-scoped state objects

Three lightweight state objects, all owned by `ResponderParent` and shared with the framework.

```python
# wrappers/protocol_parsers/http2.py — new
class Http2ConnectionState:
    """Observed client SETTINGS used by the response encoder for faithful framing.

    HPACK encoder state is intentionally NOT tracked here — _encode_header_block
    uses a per-call encoder with sensitive=True (see its docstring at
    http2.py:193-200), which is deliberate to keep synthesized responses from
    polluting the client's HPACK dynamic table. Don't add an encoder field.
    """
    def __init__(self):
        self.max_frame_size: int = 16_384        # RFC 7540 §6.5.2 default
        self.max_header_list_size: int | None = None

# wrappers/protocol_parsers/websocket.py — new
class WebSocketConnectionState:
    """Connection-scoped WebSocket negotiation captured at the 101 handshake."""
    def __init__(self):
        self.permessage_deflate_negotiated: bool = False
        self.subprotocol: str | None = None

# wrappers/protocol_parsers/mqtt.py — already exists, unchanged
# MqttConnectionState already tracks protocol_version from c2s CONNECT
```

### Wire-up

The existing `add_args()` extension point at `responder___parent.py:25-35` accepts three new kwargs:

```python
def add_args(
    self,
    engine=None,
    h2_state: Http2ConnectionState | None = None,
    mqtt_state: MqttConnectionState | None = None,
    ws_state: WebSocketConnectionState | None = None,
):
    self.engine = engine
    self._h2_state = h2_state
    self._mqtt_state = mqtt_state
    self._ws_state = ws_state
```

`connection_thread_worker.py` eagerly allocates all three state objects alongside the existing parser nonlocals (replacing the current lazy `mqtt_state = None` at line 1019), then passes them to `responder.add_args(...)` at line 1039. The existing `init_framer_for_side` (line 822-830) stops allocating its own `mqtt_state` and uses the pre-allocated one — same instance is now shared between the c2s/s2c parsers and the responder.

### State population — where each field is written

| State field | Writer | Trigger |
|---|---|---|
| `mqtt_state.protocol_version` | `MqttDirectionParser` (already does this) | Parsing c2s CONNECT |
| `h2_state.max_frame_size` | `Http2DirectionParser` (new hook in `feed()`) | c2s `SETTINGS` frame with `SETTINGS_MAX_FRAME_SIZE` |
| `h2_state.max_header_list_size` | same | `SETTINGS_MAX_HEADER_LIST_SIZE` |
| `ws_state.permessage_deflate_negotiated` | new helper called from the 101 swap at `connection_thread_worker.py:449-464` | `Sec-WebSocket-Extensions: permessage-deflate` in s2c 101 |
| `ws_state.subprotocol` | same | `Sec-WebSocket-Protocol` in s2c 101 |

### Timing guarantees

| Protocol | First responder call | State precondition |
|---|---|---|
| HTTP/1.x | After first c2s HTTP/1 request parsed | none (no session state) |
| HTTP/2 | After first c2s HEADERS with END_STREAM | Client's initial `SETTINGS` (always sent right after the preface, before any HEADERS) |
| MQTT | After first c2s packet (typically CONNECT) | CONNECT itself populates `protocol_version` before the parser yields the parsed object |
| WebSocket | After 101 handshake | The 101 response populates `ws_state` during the swap |

No races. Every state field is populated before the first response builder call that needs it.

## API Surface

All helpers are methods on `ResponderParent`. All take `class_client_message: ClientMessage` as the first positional argument and return `bytes`.

### HTTP/1.x

```python
def build_byte_response(
    self,
    class_client_message: ClientMessage,
    status_code: int,
    headers: dict | None = None,
    body: bytes = b'',
    http_version: str | None = None,  # see docstring
) -> bytes
```

| Auto-filled | Source |
|---|---|
| `http_version` | `class_client_message.request_auto_parsed.request_version` |
| Reason phrase | `HTTPStatus(status_code).phrase` (already auto today) |
| `Content-Length` header | `len(body)` — only if not in `headers` |

**`http_version` parameter:** BACKWARDS-COMPAT NO-OP. Kept in the signature so existing engines that pass `http_version=...` as a kwarg don't break with `TypeError`. Any value passed is silently discarded — the wire version is always pulled from `request_auto_parsed.request_version`. New code should omit it.

`Date` header is **not** auto-added. Real services vary in whether they send it; the engine should add it explicitly when mimicking a service that does.

### HTTP/2

```python
def build_byte_http2_response(
    self,
    class_client_message: ClientMessage,
    status_code: int,
    headers: dict | None = None,
    body: bytes = b'',
    trailers: dict | None = None,
) -> bytes
```

| Auto-filled | Source |
|---|---|
| `stream_id` | `class_client_message.request_auto_parsed.stream_id` |
| DATA frame fragmentation | `self._h2_state.max_frame_size` (from client `SETTINGS`) |
| Header block size enforcement | `self._h2_state.max_header_list_size` (refuses to encode if exceeded) |
| `content-length` regular header | `len(body)` — only if not in `headers` |

HPACK encoding stays per-call with `sensitive=True` (preserves existing correctness for mixed synthesised/forwarded traffic).

**Retired:** the explicit `stream_id` parameter.

### MQTT (broker-side)

All MQTT helpers auto-fill `protocol_version` from `self._mqtt_state.protocol_version`. Acknowledgements also auto-fill `packet_identifier` from `class_client_message.request_auto_parsed.packet_identifier`.

| Method | Engine provides | Auto-filled |
|---|---|---|
| `build_byte_mqtt_connack(msg, session_present=False, return_code=0)` | `session_present`, `return_code` | `protocol_version` |
| `build_byte_mqtt_puback(msg)` | — | `packet_identifier`, `protocol_version` |
| `build_byte_mqtt_pubrec(msg)` | — | `packet_identifier`, `protocol_version` |
| `build_byte_mqtt_pubcomp(msg)` | — | `packet_identifier`, `protocol_version` |
| `build_byte_mqtt_suback(msg, return_codes)` | `return_codes` (per-topic granted QoS) | `packet_identifier`, `protocol_version` |
| `build_byte_mqtt_unsuback(msg, return_codes=None)` | `return_codes` (v5 only) | `packet_identifier`, `protocol_version` |
| `build_byte_mqtt_pingresp(msg)` | — | (degenerate: always `0xD0 0x00`; `msg` taken for API consistency) |
| `build_byte_mqtt_publish(msg, topic, payload, qos=0, retain=False, packet_identifier=None)` | `topic`, `payload`, `qos`, `retain`; `packet_identifier` is required when `qos>0` (broker-initiated PUBLISH at QoS>0 needs an identifier the engine chooses; helper raises `ValueError` if `qos>0` and `packet_identifier is None`) | `protocol_version` |
| `build_byte_mqtt_disconnect(msg, reason_code=0)` | `reason_code` (v5 only) | `protocol_version` |

### WebSocket (server→client)

All helpers auto-fill `mask=False` (RFC 6455 §5.1) and `deflate` from `self._ws_state.permessage_deflate_negotiated`.

| Method | Engine provides | Auto-filled |
|---|---|---|
| `build_byte_websocket_frame(msg, data)` | `data: str \| bytes` | `mask=False`, `opcode` from `data` type (`str`→TEXT, `bytes`→BINARY), `deflate`, fragmentation if oversized |
| `build_byte_websocket_close(msg, code=1000, reason='')` | `code`, `reason` | `mask=False`, opcode=CLOSE, payload (2-byte big-endian `code` + `reason.encode()`) |
| `build_byte_websocket_ping(msg, data=b'')` | `data` | `mask=False`, opcode=PING |
| `build_byte_websocket_pong(msg, data=b'')` | `data` | `mask=False`, opcode=PONG |

## Reference Example Updates

The reference engine `responder___reference_general.py` is rewritten so every helper call site is preceded by a comment block enumerating exactly which fields the helper auto-fills and where each value comes from.

### HTTP/2 (replaces lines 127-176)

```python
# def create_response(self, class_client_message: ClientMessage):
#     ar = class_client_message.request_auto_parsed
#     if not isinstance(ar, http2.Http2RequestParse):
#         return None
#
#     response_bytes_list: list[bytes] = []
#
#     # 1. JSON response: synthesise a 200 OK on the same stream the client opened.
#     # Auto-filled by build_byte_http2_response:
#     #   stream_id            <- class_client_message.request_auto_parsed.stream_id
#     #   DATA fragmentation   <- self._h2_state.max_frame_size (from client SETTINGS)
#     #   content-length       <- len(body), only when absent from headers
#     # (HPACK encoding stays per-call with sensitive=True; not connection-scoped.)
#     body: bytes = b'{"ok": true}'
#     headers = {'content-type': 'application/json'}
#     response_bytes_list.append(self.build_byte_http2_response(
#         class_client_message, status_code=200, headers=headers, body=body))
#
#     # 2. Empty-body 204: same auto-fills.
#     # response_bytes_list.append(self.build_byte_http2_response(
#     #     class_client_message, status_code=204, headers={}, body=b''))
#
#     # 3. gRPC-style with trailers: same auto-fills.
#     # response_bytes_list.append(self.build_byte_http2_response(
#     #     class_client_message,
#     #     status_code=200,
#     #     headers={'content-type': 'application/grpc'},
#     #     body=b'\x00\x00\x00\x00\x05hello',
#     #     trailers={'grpc-status': '0', 'grpc-message': 'OK'}))
#
#     return response_bytes_list
```

### MQTT (replaces lines 183-253)

Every `mqtt.encode_*` call becomes `self.build_byte_mqtt_*`. Every branch carries its own auto-fill comment block. Representative branches:

```python
# def create_response(self, class_client_message: ClientMessage):
#     mp = class_client_message.request_auto_parsed
#     if not isinstance(mp, mqtt.MqttPacketParse):
#         return None
#
#     response_bytes_list: list[bytes] = []
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
#         granted = [requested_qos for _t, requested_qos in (mp.subscriptions or [])]
#         response_bytes_list.append(self.build_byte_mqtt_suback(
#             class_client_message, return_codes=granted))
#
#     # PUBACK / PUBREC for inbound PUBLISH at QoS>0.
#     # Auto-filled by build_byte_mqtt_puback / build_byte_mqtt_pubrec:
#     #   packet_identifier <- class_client_message.request_auto_parsed.packet_identifier
#     #   protocol_version  <- self._mqtt_state.protocol_version
#     elif mp.packet_type == 'PUBLISH':
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
#         # If echoing at qos>0, the engine must pass packet_identifier explicitly:
#         # response_bytes_list.append(self.build_byte_mqtt_publish(
#         #     class_client_message, topic=mp.topic, payload=mp.payload or b'',
#         #     qos=1, retain=False, packet_identifier=12345))
#
#     # PINGRESP — fixed 2 bytes (0xD0 0x00); no session state used.
#     elif mp.packet_type == 'PINGREQ':
#         response_bytes_list.append(self.build_byte_mqtt_pingresp(class_client_message))
#
#     # PUBCOMP / UNSUBACK / DISCONNECT — same auto-fill pattern; full examples in the
#     # commented section of the engine file.
#
#     return response_bytes_list
```

### WebSocket (replaces lines 90-123)

```python
# def create_response(self, class_client_message: ClientMessage):
#     ws_frame = class_client_message.request_auto_parsed
#     frame_data = ws_frame['frame']
#     frame_opcode = ws_frame['opcode']
#
#     response_bytes_list: list[bytes] = []
#
#     # Auto-filled by build_byte_websocket_frame:
#     #   mask=False (RFC 6455 §5.1 — server-side frames are never masked)
#     #   opcode    <- inferred from data type (str -> TEXT, bytes -> BINARY)
#     #   deflate   <- self._ws_state.permessage_deflate_negotiated (from 101 handshake)
#     #   FIN/continuation framing for payloads larger than MAX_FRAME_SIZE
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
```

### HTTP/1.x test response (replaces lines 388-406)

```python
# def create_response(self, class_client_message: ClientMessage):
#     resp_body: bytes = b"<html><body>TEST OK!</body></html>\n"
#     resp_headers: dict = {"Content-Type": "text/html; charset=utf-8"}
#
#     # Auto-filled by build_byte_response:
#     #   http_version    <- class_client_message.request_auto_parsed.request_version
#     #   Reason phrase   <- HTTPStatus(status_code).phrase
#     #   Content-Length  <- len(body), only when absent from headers
#     byte_response = self.build_byte_response(
#         class_client_message, status_code=200, headers=resp_headers, body=resp_body)
#     return [byte_response]
```

### HTTP/1.x dispatcher (modifies lines 349-385)

Only the `self.build_byte_response(...)` call at line 377-382 changes: drop the `http_version=...` argument, add `class_client_message` as first positional, prepend the auto-fill comment block.

## What Stays, What Retires, Error Handling

### Retired in place

| File / function | Before | After |
|---|---|---|
| `responder___parent.py: build_byte_response` | `(http_version, status_code, headers, body)` + self-parse + returns `b''` on error | `(class_client_message, status_code, headers=None, body=b'', http_version=None)`. Self-parse removed; `http_version` kept as vestigial no-op kwarg (see API section); helper raises on bad input instead of returning `b''` |
| `responder___parent.py: build_byte_http2_response` | `(status_code, headers, body, stream_id, trailers)` | `(class_client_message, status_code, headers=None, body=b'', trailers=None)` — `stream_id` removed |
| `wrappers/protocol_parsers/http2.py: encode_http2_response` | `(status_code, headers, body, stream_id, trailers)` — engine entry-point | Gains internal kwargs for connection-scoped `encoder` and `max_frame_size`. Becomes wire-layer primitive, called only by the parent helper |
| Engines: `mqtt.encode_*(packet_identifier=..., protocol_version=...)` | Direct engine call | `self.build_byte_mqtt_*(class_client_message)` |
| Engines: `websocket.create_websocket_frame(data=..., deflate=False, mask=False)` | Direct engine call | `self.build_byte_websocket_frame(class_client_message, data=...)` |
| `connection_thread_worker.py:1019` `mqtt_state = None` lazy | Lazy in `init_framer_for_side` | Eager allocation alongside new `h2_state`, `ws_state` |

### Stays

- All wire-layer encoder functions in `wrappers/protocol_parsers/{http,http2,mqtt,websocket}.py` keep emitting bytes. They become internal-by-convention.
- `MqttConnectionState` unchanged — just newly shared with the responder.
- `ResponderParent.add_args()` keeps backward-compatible kwarg-injection semantics per its own docstring.
- Receive-side parsers (`Http2DirectionParser`, `MqttDirectionParser`, framers) have no signature changes; HTTP/2 parser gains an internal SETTINGS observer with no external API change.

### New

- `Http2ConnectionState`, `WebSocketConnectionState` classes.
- Sets of `build_byte_*` methods on `ResponderParent` (per Section "API Surface").
- SETTINGS observation hook inside `Http2DirectionParser.feed()`.
- Extension/subprotocol capture inside the 101 swap at `connection_thread_worker.py:449-464`.

### Error handling — raise, don't return `b''`

Current `build_byte_response` swallows encoding errors and returns `b''` (`responder___parent.py:192-196`, `199-203`). The engine appends `b''` to its response list, and an empty response goes to the wire — a broken response reaches the client and the bug is invisible.

**New rule across all `build_byte_*` helpers: raise on any structural failure.** The framework's existing `try` at `connection_thread_worker.py:916-923` already records engine exceptions to `client_message.errors` and forwards them to the parent thread.

| Condition | Behavior |
|---|---|
| HTTP/2: `request_auto_parsed.stream_id` missing or zero | `raise ValueError("build_byte_http2_response: request_auto_parsed.stream_id required")` |
| HTTP/2: `self._h2_state` is `None` | `raise RuntimeError("build_byte_http2_response: Http2ConnectionState not wired; check add_args call")` |
| HTTP/2: header block exceeds `_h2_state.max_header_list_size` | `raise ValueError("build_byte_http2_response: header list size <n> exceeds client SETTINGS limit <m>")` |
| MQTT ack: `request_auto_parsed.packet_identifier` is `None` | `raise ValueError("<helper>: request_auto_parsed.packet_identifier required")` |
| MQTT: `_mqtt_state.protocol_version` is `None` (no CONNECT seen) | `raise RuntimeError("<helper>: protocol_version unknown; CONNECT must precede this packet")` |
| WebSocket: `data` is neither `str` nor `bytes` | `raise TypeError("build_byte_websocket_frame: data must be str or bytes")` |
| HTTP/1.x: `status_code` not in `HTTPStatus` enum | bubbles up `ValueError` from `HTTPStatus(status_code)` (current behavior, but now reaches the caller instead of being eaten) |

## Testing Strategy

### Band 1 — Unit tests for `build_byte_*` helpers (new)

For each protocol, exercise auto-fill behavior in isolation. Mock `ClientMessage` and connection-scoped state.

| Helper | Test cases |
|---|---|
| `build_byte_response` | (a) `http_version` pulled from request when omitted; (b) explicit `http_version=...` passed but silently discarded (regression for backwards-compat); (c) `Content-Length` auto-added when absent; (d) `Content-Length` left untouched when caller provided it; (e) raises `ValueError` on out-of-range `status_code` |
| `build_byte_http2_response` | (a) `stream_id` pulled from request; (b) HPACK headers still emitted with `sensitive=True` (regression test for the no-pollution invariant); (c) DATA fragmentation respects `_h2_state.max_frame_size`; (d) raises when header block exceeds `_h2_state.max_header_list_size`; (e) raises when `_h2_state` is `None` |
| `build_byte_mqtt_puback` / `pubrec` / `pubcomp` | (a) `packet_identifier` pulled from request; (b) `protocol_version` pulled from `_mqtt_state`; (c) raises when `_mqtt_state.protocol_version` is `None` |
| `build_byte_mqtt_connack` / `suback` / `unsuback` / `publish` / `disconnect` | One test per packet type; engine-supplied fields override correctly |
| `build_byte_websocket_frame` | (a) `mask=False` always; (b) opcode inferred from `str` vs `bytes`; (c) `deflate` from `_ws_state.permessage_deflate_negotiated`; (d) fragmentation above frame-size limit |
| `build_byte_websocket_close` / `ping` / `pong` | Payload encoding correctness for close frames; `data` passthrough for ping/pong |

### Band 2 — Integration tests for connection state population (new)

| Test | Setup | Assertion |
|---|---|---|
| HTTP/2 SETTINGS before first response | Feed `Http2DirectionParser` preface → SETTINGS(MAX_FRAME_SIZE=32768) → HEADERS | `h2_state.max_frame_size == 32768` before HEADERS yields a parsed object |
| HTTP/2 SETTINGS update mid-connection | Second SETTINGS frame mid-stream | `h2_state` reflects latest values |
| MQTT protocol_version from CONNECT | Feed c2s CONNECT(v5) | `mqtt_state.protocol_version == 5` before CONNACK built |
| WS extensions from 101 | s2c 101 with `Sec-WebSocket-Extensions: permessage-deflate` | `ws_state.permessage_deflate_negotiated is True` |
| WS no extension negotiated | 101 without extensions header | `ws_state.permessage_deflate_negotiated is False` |

### Band 3 — End-to-end smoke tests (new + updated)

Existing engine integration tests in `atomicshop` get their engine code rewritten to use the new helpers. Confirms:

- HTTP/1.1 GET → engine builds 200 → client receives wire-correct bytes with auto-filled `http_version` and `Content-Length`.
- HTTP/2 request → engine builds 200 → response arrives on the request's `stream_id` (not stream 1 hardcoded).
- MQTT CONNECT → CONNACK with correct `protocol_version` byte.
- WebSocket handshake with `permessage-deflate` negotiated → subsequent frames actually compressed (the test that catches the silent-`deflate=False` bug today).

### Band 4 — Backwards-compat regression (new)

One targeted test that confirms `build_byte_response(class_client_message, status_code=200, ..., http_version='HTTP/1.1')` produces output identical to one that omits `http_version`. Pins the vestigial-parameter behavior.

## Compatibility Notes

- **`build_byte_response` callers passing `http_version=class_client_message.request_auto_parsed.request_version`** continue working unchanged; the value is silently overridden by the same value.
- **`build_byte_response` callers passing `http_version='HTTP/1.0'`** (forced downgrade) — this is the one behavior change. Override is silently ignored; response now mirrors the request version. If any deployed engine relied on this, the deviation surfaces in stats/logs after deployment.
- **`build_byte_http2_response` callers passing `stream_id=...`** break with `TypeError`. Migration: drop the kwarg.
- **Engines calling `mqtt.encode_*(...)` directly** continue working — those functions are unchanged. Migration to `self.build_byte_mqtt_*(...)` is part of the engine rewrite (templates updated, deployed engines updated as they're touched).
- **Engines calling `websocket.create_websocket_frame(...)` directly** continue working. Same migration story.

## Out of Scope (Future Work)

- **Post-emission validation gate.** Detect-and-block wire-invalid bytes from any source (engine, encoder, fallback path). Records into `statistics.csv` `errors` column and CRITICAL logs via existing `print_api` mechanism. Separate spec.
- **HTTP/2 flow control / stream priority.** Requires a full h2 state machine; ruled out by the `hyperframe`+`hpack` choice at `http2.py:8-15`.
- **MQTT v5 property-list synthesis.** Stays as engine code.

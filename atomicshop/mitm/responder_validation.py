"""Post-emission validation gate for responder output.

Pure, socket-free verdict on whether one outgoing response message is safe to
send. Synthesized bytes are fresh-parsed through the matching protocol parser;
forwarded service bytes reuse the verdict the receive-side parser already
produced. Unknown/unsupported protocols are never blocked.

See docs/superpowers/specs/2026-06-03-responder-validation-gate-design.md.
"""

from dataclasses import dataclass

from ..wrappers.protocol_parsers.http import HTTPResponseParse
from ..wrappers.protocol_parsers.http2 import (
    Http2DirectionParser, validate_response_headers, validate_response_trailers)
from ..wrappers.protocol_parsers.mqtt import MqttDirectionParser
from ..wrappers.protocol_parsers.websocket import is_frame_deflated


@dataclass
class ValidationResult:
    """Verdict for one outgoing response message.

    should_send=False  -> block the send and reset the connection.
    defect             -> human-readable reason; present when blocked.
    """
    should_send: bool
    defect: str | None = None


def receive_parse_verdict(auto_parsed, protocol: str) -> bool | None:
    """Whether the receive-side parse of a forwarded response succeeded.

    Returns a bool only when there's a clean signal (HTTP/1.x, MQTT). Returns
    None otherwise — HTTP/2 failures raise upstream before reaching the gate, and
    WebSocket deflate context makes a hard verdict unreliable. None = pass.
    """
    if protocol.startswith('HTTP/1'):
        return auto_parsed is not None
    if protocol == 'MQTT':
        return auto_parsed is not None and not getattr(auto_parsed, 'error', None)
    return None


def validate_response(
        raw_bytes: bytes,
        protocol: str,
        protocol2: str,
        is_synthesized: bool,
        receive_parse_ok: bool | None,
        *,
        ws_validator=None,
) -> ValidationResult:
    """Decide whether raw_bytes is a wire-valid response for protocol."""
    # Forwarded service bytes: reuse the receive-side verdict; only block on a
    # recorded failure, pass when there's no evidence to block on.
    if not is_synthesized:
        if receive_parse_ok is False:
            return ValidationResult(False, "receive-side parse rejected the forwarded response")
        return ValidationResult(True)

    # Synthesized bytes: fresh-parse through the matching parser.
    if protocol in ('HTTP/1.0', 'HTTP/1.1'):
        return _validate_http1(raw_bytes)
    if protocol == 'HTTP/2':
        return _validate_http2(raw_bytes)
    if protocol == 'MQTT':
        return _validate_mqtt(raw_bytes)
    if protocol == 'Websocket':
        # The 101 handshake is an HTTP/1.x response; frames are WebSocket.
        if protocol2 == 'Handshake':
            return _validate_http1(raw_bytes)
        return _validate_websocket_frame(raw_bytes, ws_validator)

    # Unknown / unsupported protocol: no parser, never block.
    return ValidationResult(True)


def _validate_http1(raw_bytes: bytes) -> ValidationResult:
    _parsed, is_http, error = HTTPResponseParse(raw_bytes).parse()
    if not is_http:
        return ValidationResult(False, f"HTTP/1.x parse failed: {error}")
    return ValidationResult(True)


def _validate_http2(raw_bytes: bytes) -> ValidationResult:
    # Fresh decoder is safe: synthesized responses use never-indexed HPACK
    # literals, so no connection-scoped dynamic-table state is needed.
    parser = Http2DirectionParser(is_request_side=False)
    try:
        messages = list(parser.feed(raw_bytes))
    except Exception as e:
        return ValidationResult(False, f"HTTP/2 parse failed: {type(e).__name__}: {e}")
    if not messages:
        return ValidationResult(False, "HTTP/2 response did not complete a stream")
    # feed() validates framing/HPACK but not response semantics — the parser is a
    # permissive observer. Enforce them here so the gate matches h11 on HTTP/1.x.
    for msg in messages:
        defect = validate_response_headers(msg.raw_headers) or validate_response_trailers(msg.raw_trailers)
        if defect:
            return ValidationResult(False, f"HTTP/2 invalid response: {defect}")
    return ValidationResult(True)


def _validate_mqtt(raw_bytes: bytes) -> ValidationResult:
    parser = MqttDirectionParser(is_request_side=False)
    parsed = None
    for packet in parser.feed(raw_bytes):
        parsed = packet
    if parsed is None:
        return ValidationResult(False, "MQTT: no packet parsed")
    if parsed.error:
        return ValidationResult(False, f"MQTT parse failed: {parsed.error}")
    return ValidationResult(True)


def _validate_websocket_frame(raw_bytes: bytes, ws_validator) -> ValidationResult:
    # No validator wired -> cannot check; never block.
    if ws_validator is None:
        return ValidationResult(True)

    try:
        deflated = is_frame_deflated(raw_bytes)
    except ValueError:
        deflated = False  # too short to tell; treat as plain

    try:
        ws_validator.parse_frame_bytes(raw_bytes)
        return ValidationResult(True)
    except Exception as e:
        reason = f"WS frame parse failed: {type(e).__name__}: {e}"
        # permessage-deflate context spans frames; a fresh validator can wrongly
        # reject a legitimately compressed frame, so deflated frames are
        # record-only — surface the defect but never block.
        if deflated:
            return ValidationResult(True, f"deflated {reason} (record-only)")
        return ValidationResult(False, reason)

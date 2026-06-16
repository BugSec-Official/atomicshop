"""MQTT 3.1.1 / 5.0 sans-IO parsing.

Two public surfaces:

* `parse_fixed_header(buf)` — boundary detection for MqttFramer. Returns
  (header_length, remaining_length) or None when more bytes are needed.

* `MqttDirectionParser` — per-direction autoparser; `.feed(raw_bytes)` yields
  one `MqttPacketParse` per complete control packet handed in by the framer.
  Pair c2s + s2c parsers via a shared `MqttConnectionState` so the version
  negotiated by the client's CONNECT applies to both directions.

Why hand-rolled dispatch instead of `mqttools.common.unpack_publish` etc.:
those high-level helpers are MQTT 5.0-only and reject QoS > 0 PUBLISH. We
keep mqttools' primitives (`unpack_string`, `unpack_u8/16/32`, `unpack_binary`,
`unpack_variable_integer`, `PayloadReader`) — they are version-agnostic — and
dispatch packet layouts against the spec ourselves.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from io import BytesIO

from mqttools.common import (
    MalformedPacketError,
    PayloadReader,
    pack_binary,
    pack_string,
    pack_u8,
    pack_u16,
    pack_variable_integer,
    unpack_binary,
    unpack_string,
    unpack_u8,
    unpack_u16,
    unpack_variable_integer,
)


# === Fixed-header parser (MQTT 3.1.1 §2.2 / 5.0 §2.1) ===
# Sans-IO primitive: tell the framer how many bytes one control packet occupies.

_MAX_VBI_BYTES = 4  # Remaining Length VBI is at most 4 bytes (max value 268_435_455).


def parse_fixed_header(buf) -> tuple[int, int] | None:
    """Return (header_length, remaining_length) or None if buf doesn't yet hold a full fixed header.

    header_length = 1 type/flags byte + 1-4 VBI bytes; remaining_length is the
    variable header + payload size to follow. Raises ValueError when the 4th VBI
    byte still has the continuation bit set (malformed per spec).
    """
    n = len(buf)
    if n < 2:
        return None
    # Cap probe at 4 VBI bytes; mqttools loops on the 0x80 continuation bit.
    vbi_slice = bytes(buf[1:1 + _MAX_VBI_BYTES])
    stream = BytesIO(vbi_slice)
    try:
        remaining = unpack_variable_integer(stream)
    except IndexError:
        # Ran out of bytes in the 4-byte window. If we offered the full 4 and it
        # still wanted more, the 4th byte's continuation bit was set -> spec violation.
        if len(vbi_slice) == _MAX_VBI_BYTES:
            raise ValueError("MQTT remaining length VBI exceeds 4 bytes")
        return None
    return 1 + stream.tell(), remaining


# === Signature detection ===
# Tri-state: True = match, False = mismatch, None = need more bytes.

def detect_mqtt_connect(buf: bytes) -> bool | None:
    """MQTT CONNECT: 0x10 + VBI remaining length + 'MQTT' (3.1.1/5.0) or 'MQIsdp' (3.1)."""
    if len(buf) < 2:
        return None
    if buf[0] != 0x10:
        return False
    # Remaining-length VBI: 1-4 bytes, 7 bits + continuation bit per byte.
    pos = 1
    while True:
        if pos >= len(buf):
            return None
        if pos > 4:
            return False  # spec caps VBI at 4 bytes
        byte = buf[pos]
        pos += 1
        if byte & 0x80 == 0:
            break
    # Variable header: 2-byte name length (big-endian) + name.
    if len(buf) < pos + 2:
        return None
    name_len = (buf[pos] << 8) | buf[pos + 1]
    if name_len not in (4, 6):  # MQTT=4, MQIsdp=6
        return False
    if len(buf) < pos + 2 + name_len:
        return None
    name = bytes(buf[pos + 2: pos + 2 + name_len])
    return name in (b'MQTT', b'MQIsdp')


def detect_mqtt_connack(buf: bytes) -> bool | None:
    """MQTT CONNACK: 0x20 + remaining length 2 (3.1.1) or 3 (5.0)."""
    if len(buf) < 2:
        return None
    if buf[0] != 0x20:
        return False
    return buf[1] in (2, 3)


# === Protocol version constants (MQTT 3.1.1 §3.1.2.2 / 5.0 §3.1.2.2) ===
PROTOCOL_VERSION_3_1 = 3      # legacy 'MQIsdp'
PROTOCOL_VERSION_3_1_1 = 4
PROTOCOL_VERSION_5 = 5


# === Packet type IDs (MQTT 3.1.1 §2.2.1 / 5.0 §2.1.2) ===
PACKET_TYPE_CONNECT = 1
PACKET_TYPE_CONNACK = 2
PACKET_TYPE_PUBLISH = 3
PACKET_TYPE_PUBACK = 4
PACKET_TYPE_PUBREC = 5
PACKET_TYPE_PUBREL = 6
PACKET_TYPE_PUBCOMP = 7
PACKET_TYPE_SUBSCRIBE = 8
PACKET_TYPE_SUBACK = 9
PACKET_TYPE_UNSUBSCRIBE = 10
PACKET_TYPE_UNSUBACK = 11
PACKET_TYPE_PINGREQ = 12
PACKET_TYPE_PINGRESP = 13
PACKET_TYPE_DISCONNECT = 14
PACKET_TYPE_AUTH = 15  # v5 only

_PACKET_TYPE_NAMES = {
    PACKET_TYPE_CONNECT: 'CONNECT',
    PACKET_TYPE_CONNACK: 'CONNACK',
    PACKET_TYPE_PUBLISH: 'PUBLISH',
    PACKET_TYPE_PUBACK: 'PUBACK',
    PACKET_TYPE_PUBREC: 'PUBREC',
    PACKET_TYPE_PUBREL: 'PUBREL',
    PACKET_TYPE_PUBCOMP: 'PUBCOMP',
    PACKET_TYPE_SUBSCRIBE: 'SUBSCRIBE',
    PACKET_TYPE_SUBACK: 'SUBACK',
    PACKET_TYPE_UNSUBSCRIBE: 'UNSUBSCRIBE',
    PACKET_TYPE_UNSUBACK: 'UNSUBACK',
    PACKET_TYPE_PINGREQ: 'PINGREQ',
    PACKET_TYPE_PINGRESP: 'PINGRESP',
    PACKET_TYPE_DISCONNECT: 'DISCONNECT',
    PACKET_TYPE_AUTH: 'AUTH',
}


# === CONNECT Flags byte (§3.1.2.3) ===
_CONNECT_FLAG_CLEAN_SESSION = 0x02
_CONNECT_FLAG_WILL          = 0x04
_CONNECT_FLAG_WILL_RETAIN   = 0x20
_CONNECT_FLAG_PASSWORD      = 0x40
_CONNECT_FLAG_USERNAME      = 0x80
_CONNECT_FLAG_WILL_QOS_MASK = 0x18  # bits 4-3


# === PUBLISH fixed-header low nibble (§3.3.1) ===
_PUBLISH_FLAG_DUP    = 0x08
_PUBLISH_QOS_MASK    = 0x06  # bits 2-1
_PUBLISH_FLAG_RETAIN = 0x01


@dataclass
class MqttPacketParse:
    """One parsed MQTT control packet. Fields are populated per packet_type; unused stay None."""

    # Always populated
    raw_bytes: bytes = b''
    packet_type: str = ''
    packet_type_id: int = 0
    flags: int = 0
    remaining_length: int = 0
    protocol_version: int = 0
    error: str | None = None

    # CONNECT
    client_id: str | None = None
    clean_session: bool | None = None    # v3 'Clean Session' / v5 'Clean Start'
    keep_alive_s: int | None = None
    will_topic: str | None = None
    will_message: bytes | None = None
    will_qos: int | None = None
    will_retain: bool | None = None
    username: str | None = None
    password: bytes | None = None        # binary per spec; may be utf-8 in practice

    # CONNACK
    session_present: bool | None = None
    return_code: int | None = None       # v3 connect return code (§3.2.2.3)

    # PUBLISH (extras beyond packet_identifier)
    dup: bool | None = None
    qos: int | None = None
    retain: bool | None = None
    topic: str | None = None
    payload: bytes | None = None

    # PUBLISH(QoS>0) / PUBACK / PUBREC / PUBREL / PUBCOMP / SUBSCRIBE / SUBACK / UNSUBSCRIBE / UNSUBACK
    packet_identifier: int | None = None

    # SUBSCRIBE
    subscriptions: list[tuple[str, int]] | None = None   # (topic_filter, requested_qos)

    # SUBACK / UNSUBACK (return codes / reason codes per topic)
    return_codes: list[int] | None = None

    # UNSUBSCRIBE
    topic_filters: list[str] | None = None

    # v5 reason codes (single-byte): PUBACK/PUBREC/PUBREL/PUBCOMP, DISCONNECT, AUTH, CONNACK
    reason_code: int | None = None

    # v5 Properties — kept as raw bytes; full per-property decoding is a follow-up.
    properties_raw: bytes | None = None


class MqttConnectionState:
    """Per-connection state shared between c2s and s2c parsers — currently the negotiated protocol version."""

    def __init__(self, protocol_version: int = PROTOCOL_VERSION_3_1_1):
        # Default to v3.1.1; updated when CONNECT is observed on the c2s side.
        self.protocol_version: int = protocol_version


class MqttDirectionParser:
    """Sans-IO MQTT autoparser for one direction.

    Mirrors `http2.Http2DirectionParser`. Feed one complete
    control packet's wire bytes (as produced by MqttFramer); receive exactly
    one parsed MqttPacketParse per call. The c2s parser detects the protocol
    version from CONNECT and stamps it onto the shared state so the s2c side
    interprets CONNACK / PUBACK / etc. correctly.
    """

    def __init__(self, is_request_side: bool, state: MqttConnectionState | None = None):
        self._is_request_side = is_request_side
        self._state = state if state is not None else MqttConnectionState()

    @property
    def state(self) -> MqttConnectionState:
        return self._state

    def feed(self, raw_bytes: bytes) -> Iterator[MqttPacketParse]:
        out = MqttPacketParse(raw_bytes=raw_bytes)
        try:
            self._parse_one(raw_bytes, out)
        except (MalformedPacketError, ValueError, IndexError, UnicodeDecodeError) as e:
            out.error = f'{type(e).__name__}: {e}'
        yield out

    # --- internals ---

    def _parse_one(self, raw: bytes, out: MqttPacketParse) -> None:
        fh = parse_fixed_header(raw)
        if fh is None:
            raise MalformedPacketError('Incomplete fixed header')
        header_len, remaining = fh
        if len(raw) != header_len + remaining:
            raise MalformedPacketError(
                f'Body length mismatch: expected {header_len + remaining}, got {len(raw)}')

        first = raw[0]
        type_id = first >> 4
        flags = first & 0x0F
        out.packet_type_id = type_id
        out.packet_type = _PACKET_TYPE_NAMES.get(type_id, f'UNKNOWN({type_id})')
        out.flags = flags
        out.remaining_length = remaining
        out.protocol_version = self._state.protocol_version

        body = PayloadReader(raw[header_len:])

        if type_id == PACKET_TYPE_CONNECT:
            self._parse_connect(body, out)
        elif type_id == PACKET_TYPE_CONNACK:
            self._parse_connack(body, out)
        elif type_id == PACKET_TYPE_PUBLISH:
            self._parse_publish(body, out, flags)
        elif type_id in (PACKET_TYPE_PUBACK, PACKET_TYPE_PUBREC, PACKET_TYPE_PUBREL, PACKET_TYPE_PUBCOMP):
            self._parse_pubxxx(body, out)
        elif type_id == PACKET_TYPE_SUBSCRIBE:
            self._parse_subscribe(body, out)
        elif type_id == PACKET_TYPE_SUBACK:
            self._parse_suback(body, out)
        elif type_id == PACKET_TYPE_UNSUBSCRIBE:
            self._parse_unsubscribe(body, out)
        elif type_id == PACKET_TYPE_UNSUBACK:
            self._parse_unsuback(body, out)
        elif type_id in (PACKET_TYPE_PINGREQ, PACKET_TYPE_PINGRESP):
            pass  # No variable header, no payload.
        elif type_id == PACKET_TYPE_DISCONNECT:
            self._parse_disconnect(body, out)
        elif type_id == PACKET_TYPE_AUTH:
            self._parse_auth(body, out)
        else:
            raise MalformedPacketError(f'Reserved/unknown packet type id {type_id}')

    # CONNECT — §3.1
    def _parse_connect(self, body: PayloadReader, out: MqttPacketParse) -> None:
        protocol_name = unpack_string(body)  # 'MQTT' (v3.1.1/v5) or 'MQIsdp' (v3.1)
        version = unpack_u8(body)
        self._state.protocol_version = version
        out.protocol_version = version
        flags = unpack_u8(body)
        out.clean_session = bool(flags & _CONNECT_FLAG_CLEAN_SESSION)
        out.keep_alive_s = unpack_u16(body)

        if version == PROTOCOL_VERSION_5:
            out.properties_raw = _read_properties_blob(body)

        out.client_id = unpack_string(body)

        if flags & _CONNECT_FLAG_WILL:
            if version == PROTOCOL_VERSION_5:
                _read_properties_blob(body)  # will-properties; discarded for now
            out.will_topic = unpack_string(body)
            out.will_message = unpack_binary(body)
            out.will_qos = (flags & _CONNECT_FLAG_WILL_QOS_MASK) >> 3
            out.will_retain = bool(flags & _CONNECT_FLAG_WILL_RETAIN)

        if flags & _CONNECT_FLAG_USERNAME:
            out.username = unpack_string(body)
        if flags & _CONNECT_FLAG_PASSWORD:
            out.password = unpack_binary(body)

        # Suppress unused-name warning; tracking the protocol_name isn't useful downstream.
        del protocol_name

    # CONNACK — §3.2
    def _parse_connack(self, body: PayloadReader, out: MqttPacketParse) -> None:
        ack_flags = unpack_u8(body)
        out.session_present = bool(ack_flags & 0x01)
        code = unpack_u8(body)
        # Same byte in v3 (Connect Return Code) and v5 (Connect Reason Code) — surface both names.
        out.return_code = code
        out.reason_code = code
        if body.is_data_available():
            # Only v5 emits trailing properties; mark the connection v5 if c2s missed CONNECT.
            self._state.protocol_version = PROTOCOL_VERSION_5
            out.protocol_version = PROTOCOL_VERSION_5
            out.properties_raw = _read_properties_blob(body)

    # PUBLISH — §3.3
    def _parse_publish(self, body: PayloadReader, out: MqttPacketParse, flags: int) -> None:
        qos = (flags & _PUBLISH_QOS_MASK) >> 1
        out.dup = bool(flags & _PUBLISH_FLAG_DUP)
        out.qos = qos
        out.retain = bool(flags & _PUBLISH_FLAG_RETAIN)
        out.topic = unpack_string(body)
        if qos > 0:
            out.packet_identifier = unpack_u16(body)
        if self._state.protocol_version == PROTOCOL_VERSION_5:
            out.properties_raw = _read_properties_blob(body)
        out.payload = body.read_all()

    # PUBACK / PUBREC / PUBREL / PUBCOMP — §3.4 / §3.5 / §3.6 / §3.7
    def _parse_pubxxx(self, body: PayloadReader, out: MqttPacketParse) -> None:
        out.packet_identifier = unpack_u16(body)
        # v5: optional reason code + optional properties when remaining length > 2.
        if self._state.protocol_version == PROTOCOL_VERSION_5 and body.is_data_available():
            out.reason_code = unpack_u8(body)
            if body.is_data_available():
                out.properties_raw = _read_properties_blob(body)

    # SUBSCRIBE — §3.8
    def _parse_subscribe(self, body: PayloadReader, out: MqttPacketParse) -> None:
        out.packet_identifier = unpack_u16(body)
        if self._state.protocol_version == PROTOCOL_VERSION_5:
            out.properties_raw = _read_properties_blob(body)
        subs: list[tuple[str, int]] = []
        while body.is_data_available():
            topic = unpack_string(body)
            opts = unpack_u8(body)
            subs.append((topic, opts & 0x03))  # qos in the low 2 bits; v5 adds NL/RAP/RH above
        out.subscriptions = subs

    # SUBACK — §3.9
    def _parse_suback(self, body: PayloadReader, out: MqttPacketParse) -> None:
        out.packet_identifier = unpack_u16(body)
        if self._state.protocol_version == PROTOCOL_VERSION_5:
            out.properties_raw = _read_properties_blob(body)
        out.return_codes = _read_remaining_bytes_as_list(body)

    # UNSUBSCRIBE — §3.10
    def _parse_unsubscribe(self, body: PayloadReader, out: MqttPacketParse) -> None:
        out.packet_identifier = unpack_u16(body)
        if self._state.protocol_version == PROTOCOL_VERSION_5:
            out.properties_raw = _read_properties_blob(body)
        filters: list[str] = []
        while body.is_data_available():
            filters.append(unpack_string(body))
        out.topic_filters = filters

    # UNSUBACK — §3.11
    def _parse_unsuback(self, body: PayloadReader, out: MqttPacketParse) -> None:
        out.packet_identifier = unpack_u16(body)
        if self._state.protocol_version == PROTOCOL_VERSION_5:
            out.properties_raw = _read_properties_blob(body)
            out.return_codes = _read_remaining_bytes_as_list(body)
        # v3.1.1 UNSUBACK has no per-topic codes; return_codes stays None.

    # DISCONNECT — §3.14
    def _parse_disconnect(self, body: PayloadReader, out: MqttPacketParse) -> None:
        # v3: empty body. v5: optional reason code, optional properties.
        if self._state.protocol_version == PROTOCOL_VERSION_5 and body.is_data_available():
            out.reason_code = unpack_u8(body)
            if body.is_data_available():
                out.properties_raw = _read_properties_blob(body)

    # AUTH — §3.15 (v5 only)
    def _parse_auth(self, body: PayloadReader, out: MqttPacketParse) -> None:
        out.protocol_version = PROTOCOL_VERSION_5
        if body.is_data_available():
            out.reason_code = unpack_u8(body)
        if body.is_data_available():
            out.properties_raw = _read_properties_blob(body)


def _read_properties_blob(body: PayloadReader) -> bytes:
    """Read a v5 Properties section: VBI length + that many bytes; return the raw payload (no VBI)."""
    props_len = unpack_variable_integer(body)
    return body.read(props_len) if props_len else b''


def _read_remaining_bytes_as_list(body: PayloadReader) -> list[int]:
    return list(body.read_all())


# ============================================================================
# Encoder side: inverse of MqttDirectionParser.
# One function per control packet type; each takes structured fields and emits
# wire bytes. Default protocol_version is 4 (v3.1.1); pass 5 to enable the
# trailing properties section. `properties_raw` is bytes only — full property
# serialization is left to the caller (or mqttools.common.pack_properties).
# ============================================================================


def _encode_properties_blob(properties_raw: bytes) -> bytes:
    """v5 Properties section: VBI(length) + bytes."""
    return pack_variable_integer(len(properties_raw)) + properties_raw


def _encode_fixed_header(packet_type_id: int, flags: int, body_len: int) -> bytes:
    """Type<<4 | low-nibble flags, then Remaining-Length VBI."""
    if not 0 <= packet_type_id <= 15:
        raise ValueError(f"packet_type_id must be 0-15, got {packet_type_id}")
    return bytes([(packet_type_id << 4) | (flags & 0x0F)]) + pack_variable_integer(body_len)


def encode_connect(
        client_id: str,
        clean_session: bool = True,
        keep_alive_s: int = 60,
        username: str | None = None,
        password: bytes | None = None,
        will_topic: str | None = None,
        will_message: bytes | None = None,
        will_qos: int = 0,
        will_retain: bool = False,
        protocol_version: int = PROTOCOL_VERSION_3_1_1,
        properties_raw: bytes = b'',
        will_properties_raw: bytes = b'',
) -> bytes:
    """Encode a CONNECT (§3.1). Default v3.1.1 protocol name 'MQTT'."""
    proto_name = 'MQIsdp' if protocol_version == PROTOCOL_VERSION_3_1 else 'MQTT'

    flags = 0
    if clean_session:
        flags |= _CONNECT_FLAG_CLEAN_SESSION
    if will_topic is not None:
        flags |= _CONNECT_FLAG_WILL
        flags |= (will_qos & 0x03) << 3
        if will_retain:
            flags |= _CONNECT_FLAG_WILL_RETAIN
    if username is not None:
        flags |= _CONNECT_FLAG_USERNAME
    if password is not None:
        flags |= _CONNECT_FLAG_PASSWORD

    body = pack_string(proto_name) + pack_u8(protocol_version) + pack_u8(flags) + pack_u16(keep_alive_s)
    if protocol_version == PROTOCOL_VERSION_5:
        body += _encode_properties_blob(properties_raw)
    body += pack_string(client_id)
    if will_topic is not None:
        if protocol_version == PROTOCOL_VERSION_5:
            body += _encode_properties_blob(will_properties_raw)
        body += pack_string(will_topic) + pack_binary(will_message or b'')
    if username is not None:
        body += pack_string(username)
    if password is not None:
        body += pack_binary(password)

    return _encode_fixed_header(PACKET_TYPE_CONNECT, 0, len(body)) + body


def encode_connack(
        session_present: bool = False,
        return_code: int = 0,
        protocol_version: int = PROTOCOL_VERSION_3_1_1,
        properties_raw: bytes = b'',
) -> bytes:
    """Encode a CONNACK (§3.2). return_code is the v3 'Connect Return Code' or v5 'Reason Code'."""
    body = pack_u8(0x01 if session_present else 0x00) + pack_u8(return_code)
    if protocol_version == PROTOCOL_VERSION_5:
        body += _encode_properties_blob(properties_raw)
    return _encode_fixed_header(PACKET_TYPE_CONNACK, 0, len(body)) + body


def encode_publish(
        topic: str,
        payload: bytes = b'',
        qos: int = 0,
        retain: bool = False,
        dup: bool = False,
        packet_identifier: int | None = None,
        protocol_version: int = PROTOCOL_VERSION_3_1_1,
        properties_raw: bytes = b'',
) -> bytes:
    """Encode a PUBLISH (§3.3). packet_identifier is required when qos > 0."""
    if qos not in (0, 1, 2):
        raise ValueError(f"qos must be 0/1/2, got {qos}")
    if qos > 0 and packet_identifier is None:
        raise ValueError("PUBLISH with QoS > 0 requires packet_identifier")

    flags = (_PUBLISH_FLAG_DUP if dup else 0) | ((qos & 0x03) << 1) | (_PUBLISH_FLAG_RETAIN if retain else 0)
    body = pack_string(topic)
    if qos > 0:
        body += pack_u16(packet_identifier)
    if protocol_version == PROTOCOL_VERSION_5:
        body += _encode_properties_blob(properties_raw)
    body += payload

    return _encode_fixed_header(PACKET_TYPE_PUBLISH, flags, len(body)) + body


def _encode_pubxxx(
        type_id: int,
        flags: int,
        packet_identifier: int,
        reason_code: int = 0,
        protocol_version: int = PROTOCOL_VERSION_3_1_1,
        properties_raw: bytes = b'',
) -> bytes:
    body = pack_u16(packet_identifier)
    # v5: omit trailing reason_code + properties when both are defaults (§3.4.2.1 / 3.4.2.2).
    if protocol_version == PROTOCOL_VERSION_5 and (reason_code != 0 or properties_raw):
        body += pack_u8(reason_code) + _encode_properties_blob(properties_raw)
    return _encode_fixed_header(type_id, flags, len(body)) + body


def encode_puback(
        packet_identifier: int,
        reason_code: int = 0,
        protocol_version: int = PROTOCOL_VERSION_3_1_1,
        properties_raw: bytes = b'',
) -> bytes:
    """Encode a PUBACK (§3.4) — QoS 1 acknowledgement."""
    return _encode_pubxxx(PACKET_TYPE_PUBACK, 0, packet_identifier, reason_code, protocol_version, properties_raw)


def encode_pubrec(
        packet_identifier: int,
        reason_code: int = 0,
        protocol_version: int = PROTOCOL_VERSION_3_1_1,
        properties_raw: bytes = b'',
) -> bytes:
    """Encode a PUBREC (§3.5) — first half of QoS 2 handshake."""
    return _encode_pubxxx(PACKET_TYPE_PUBREC, 0, packet_identifier, reason_code, protocol_version, properties_raw)


def encode_pubrel(
        packet_identifier: int,
        reason_code: int = 0,
        protocol_version: int = PROTOCOL_VERSION_3_1_1,
        properties_raw: bytes = b'',
) -> bytes:
    """Encode a PUBREL (§3.6) — second half of QoS 2 handshake. Fixed-header flags MUST be 0x2."""
    return _encode_pubxxx(PACKET_TYPE_PUBREL, 0x2, packet_identifier, reason_code, protocol_version, properties_raw)


def encode_pubcomp(
        packet_identifier: int,
        reason_code: int = 0,
        protocol_version: int = PROTOCOL_VERSION_3_1_1,
        properties_raw: bytes = b'',
) -> bytes:
    """Encode a PUBCOMP (§3.7) — final ack of QoS 2 handshake."""
    return _encode_pubxxx(PACKET_TYPE_PUBCOMP, 0, packet_identifier, reason_code, protocol_version, properties_raw)


def encode_subscribe(
        packet_identifier: int,
        subscriptions: list[tuple[str, int]],
        protocol_version: int = PROTOCOL_VERSION_3_1_1,
        properties_raw: bytes = b'',
) -> bytes:
    """Encode a SUBSCRIBE (§3.8). subscriptions = [(topic_filter, requested_qos), ...].

    For v5, only the low 2 bits (QoS) are written into the Subscription Options
    byte — the NL / RAP / Retain Handling bits stay zero. Pre-build the bytes
    yourself if you need those.
    """
    if not subscriptions:
        raise ValueError("SUBSCRIBE must contain at least one topic filter")
    body = pack_u16(packet_identifier)
    if protocol_version == PROTOCOL_VERSION_5:
        body += _encode_properties_blob(properties_raw)
    for topic_filter, requested_qos in subscriptions:
        body += pack_string(topic_filter) + pack_u8(requested_qos & 0x03)
    return _encode_fixed_header(PACKET_TYPE_SUBSCRIBE, 0x2, len(body)) + body  # flags MUST be 0x2


def encode_suback(
        packet_identifier: int,
        return_codes: list[int],
        protocol_version: int = PROTOCOL_VERSION_3_1_1,
        properties_raw: bytes = b'',
) -> bytes:
    """Encode a SUBACK (§3.9). One return-code byte per topic in the original SUBSCRIBE."""
    body = pack_u16(packet_identifier)
    if protocol_version == PROTOCOL_VERSION_5:
        body += _encode_properties_blob(properties_raw)
    body += bytes(return_codes)
    return _encode_fixed_header(PACKET_TYPE_SUBACK, 0, len(body)) + body


def encode_unsubscribe(
        packet_identifier: int,
        topic_filters: list[str],
        protocol_version: int = PROTOCOL_VERSION_3_1_1,
        properties_raw: bytes = b'',
) -> bytes:
    """Encode an UNSUBSCRIBE (§3.10). Fixed-header flags MUST be 0x2."""
    if not topic_filters:
        raise ValueError("UNSUBSCRIBE must contain at least one topic filter")
    body = pack_u16(packet_identifier)
    if protocol_version == PROTOCOL_VERSION_5:
        body += _encode_properties_blob(properties_raw)
    for f in topic_filters:
        body += pack_string(f)
    return _encode_fixed_header(PACKET_TYPE_UNSUBSCRIBE, 0x2, len(body)) + body


def encode_unsuback(
        packet_identifier: int,
        return_codes: list[int] | None = None,
        protocol_version: int = PROTOCOL_VERSION_3_1_1,
        properties_raw: bytes = b'',
) -> bytes:
    """Encode an UNSUBACK (§3.11). v3.1.1: packet id only. v5: also per-topic reason codes."""
    body = pack_u16(packet_identifier)
    if protocol_version == PROTOCOL_VERSION_5:
        body += _encode_properties_blob(properties_raw)
        if return_codes:
            body += bytes(return_codes)
    return _encode_fixed_header(PACKET_TYPE_UNSUBACK, 0, len(body)) + body


def encode_pingreq() -> bytes:
    """Encode a PINGREQ (§3.12) — keep-alive heartbeat. Always exactly 2 bytes."""
    return _encode_fixed_header(PACKET_TYPE_PINGREQ, 0, 0)


def encode_pingresp() -> bytes:
    """Encode a PINGRESP (§3.13). Always exactly 2 bytes."""
    return _encode_fixed_header(PACKET_TYPE_PINGRESP, 0, 0)


def encode_disconnect(
        reason_code: int = 0,
        protocol_version: int = PROTOCOL_VERSION_3_1_1,
        properties_raw: bytes = b'',
) -> bytes:
    """Encode a DISCONNECT (§3.14). v3.1.1: empty body. v5: optional reason code + properties."""
    if protocol_version == PROTOCOL_VERSION_5 and (reason_code != 0 or properties_raw):
        body = pack_u8(reason_code) + _encode_properties_blob(properties_raw)
    else:
        body = b''
    return _encode_fixed_header(PACKET_TYPE_DISCONNECT, 0, len(body)) + body


def encode_auth(
        reason_code: int = 0,
        properties_raw: bytes = b'',
) -> bytes:
    """Encode an AUTH (§3.15) — v5 only, enhanced auth exchange."""
    if reason_code == 0 and not properties_raw:
        body = b''  # spec allows empty body when rc=0 and no properties
    else:
        body = pack_u8(reason_code) + _encode_properties_blob(properties_raw)
    return _encode_fixed_header(PACKET_TYPE_AUTH, 0, len(body)) + body

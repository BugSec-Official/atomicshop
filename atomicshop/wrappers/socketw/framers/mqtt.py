from collections.abc import Iterator

from ...protocol_parsers.mqtt import parse_fixed_header
from .base import Direction, Framer


# === MQTT framer (3.1.1 / 5.0 §2.1) ===
# Fixed header = 1 byte (type<<4 | flags) + Variable Byte Integer Remaining Length
# (1-4 bytes); body = exactly remaining-length bytes. Several control packets can
# share one TCP write (e.g. CONNECT+SUBSCRIBE or PUBLISH+PINGREQ); one packet can
# span many recvs. Symmetric in both directions — direction is unused. Pair with
# mqttools.common.unpack_* in the autoparser for CONNECT/PUBLISH/SUBSCRIBE decoding.


class MqttFramer(Framer):
    """MQTT 3.1.1 / 5.0 control-packet framer; emits raw wire bytes per packet."""

    def __init__(self, direction: Direction):
        del direction
        self._buf = bytearray()

    def consume(self, chunk: bytes) -> list[bytes]:
        self._buf.extend(chunk)
        return list(self._extract())

    @property
    def buffered(self) -> bytes:
        return bytes(self._buf)

    # --- internals ---

    def _extract(self) -> Iterator[bytes]:
        while True:
            parsed = parse_fixed_header(self._buf)
            if parsed is None:
                return
            header_len, remaining = parsed
            total = header_len + remaining
            if len(self._buf) < total:
                return
            yield bytes(self._buf[:total])
            del self._buf[:total]

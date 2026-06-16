import threading

from ...protocol_parsers.http import detect_http_request_line, detect_http_response_line
from ...protocol_parsers.mqtt import detect_mqtt_connack, detect_mqtt_connect
from .base import Direction, Framer


# === Protocol sniffer ===
# Callable: bytes -> Framer | None. Returns the matching framer when detection
# succeeds, None when still uncertain (more bytes needed). Cross-direction
# coordination via SharedProtocolState; one leg's detection short-circuits
# the other. Receiver enforces byte / idle-quiet caps.


def _opposite(direction: Direction) -> Direction:
    return 'server_to_client' if direction == 'client_to_server' else 'client_to_server'


class SharedProtocolState:
    """Connection-scoped protocol identification, shared between c2s and s2c sniffers."""

    def __init__(self):
        self._lock: threading.Lock = threading.Lock()
        self.protocol: str | None = None         # 'http' | 'mqtt' | None
        self.http_version: str | None = None     # 'http1' | 'http2' | None
        self.request_side: Direction | None = None  # wire leg carrying requests; None until detected
        self.server_has_spoken: bool = False     # set when s2c receives its first byte

    def set_protocol(self, name: str | None) -> None:
        with self._lock:
            self.protocol = name

    def set_http_version(self, ver: str | None) -> None:
        with self._lock:
            self.http_version = ver

    def set_request_side(self, direction: Direction | None) -> None:
        with self._lock:
            self.request_side = direction

    def mark_server_spoken(self) -> None:
        # Single attribute write; CPython makes this atomic.
        self.server_has_spoken = True


class ProtocolSniffer:
    """Per-direction byte-signature matcher; shares identification across legs via SharedProtocolState."""

    def __init__(self, direction: Direction, shared: SharedProtocolState):
        self._direction: Direction = direction
        self._shared: SharedProtocolState = shared

    def __call__(self, buf: bytes) -> Framer | None:
        if self._direction == 'server_to_client' and buf:
            self._shared.mark_server_spoken()

        # Cross-direction short-circuit: other leg already identified.
        if self._shared.protocol == 'http':
            return self._make_http()
        if self._shared.protocol == 'mqtt':
            from .mqtt import MqttFramer
            return MqttFramer(direction=self._direction)

        # HTTP by content, side-agnostic. The status line ('HTTP/') is the
        # specific shape, so test it first — the request-line heuristic also
        # matches a status line. Whichever shape a leg shows fixes the orientation.
        if detect_http_response_line(buf) is True:
            self._identify_http(request_side=_opposite(self._direction))
            return self._make_http()
        if detect_http_request_line(buf) is True:
            self._identify_http(request_side=self._direction)
            return self._make_http()

        # MQTT (direction-specific signatures).
        if self._direction == 'client_to_server':
            if detect_mqtt_connect(buf) is True:
                self._shared.set_protocol('mqtt')
                from .mqtt import MqttFramer
                return MqttFramer(direction=self._direction)
        elif detect_mqtt_connack(buf) is True:
            self._shared.set_protocol('mqtt')
            from .mqtt import MqttFramer
            return MqttFramer(direction=self._direction)

        return None

    def _identify_http(self, request_side: Direction) -> None:
        """Publish orientation before protocol so the other leg's short-circuit
        never sees HTTP without a request_side."""
        self._shared.set_request_side(request_side)
        self._shared.set_protocol('http')

    def _make_http(self) -> Framer:
        from .http import HttpFramer
        return HttpFramer(direction=self._direction, shared=self._shared)

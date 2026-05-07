from collections.abc import Iterator

from ....websocket_parse import WebsocketMessageAssembler
from .base import Framer


class WebSocketFramer(Framer):
    """
    WebSocket frame-boundary framer (RFC 6455 §5).

    Adapter to the Framer contract. Frame parsing + fragment assembly live
    in atomicshop.websocket_parse.WebsocketMessageAssembler; engines that
    need decoded payloads pass emitted bytes through
    atomicshop.websocket_parse.WebsocketFrameParser (handles unmask +
    permessage-deflate).

    is_client_to_server is informational only — masking is read per-frame
    from each frame's MASK bit, not pre-determined.
    """

    def __init__(self, is_client_to_server: bool):
        self._is_client = is_client_to_server
        self._assembler = WebsocketMessageAssembler()

    def consume(self, chunk: bytes) -> Iterator[bytes]:
        yield from self._assembler.feed(chunk)

    @property
    def buffered(self) -> bytes:
        return self._assembler.buffered

from typing import Literal


Direction = Literal['client_to_server', 'server_to_client']


# === Framer protocol ===
# Stateful protocol parser; auto-selected at runtime.

class Framer:
    """Stateful framer: consume bytes, emit complete messages.

    Contract: consume() never returns partial messages; finish() is called
    once on peer EOF; buffered is truthy iff a partial message is in flight.
    """

    def consume(self, chunk: bytes) -> list[bytes]:
        """Push chunk; return zero or more complete messages."""
        raise NotImplementedError

    def finish(self) -> list[bytes]:
        """Drain on peer EOF; return any final messages (e.g., body-until-close)."""
        return []

    @property
    def buffered(self) -> bytes:
        """Bytes accepted but not yet emitted; truthy = partial in progress."""
        return b''

from collections.abc import Iterator


# === Framer protocol ===
# Stateful protocol parser; auto-selected at runtime.

class Framer:
    """Stateful framer: consume bytes, yield complete messages."""

    def consume(self, chunk: bytes) -> Iterator[bytes]:
        """Push chunk; yield zero or more complete messages."""
        raise NotImplementedError

    def finish(self) -> Iterator[bytes]:
        """Drain on peer EOF; yield any final messages (e.g., body-until-close)."""
        return iter(())

    @property
    def buffered(self) -> bytes:
        """Bytes accepted but not yet emitted; truthy = partial in progress."""
        return b''

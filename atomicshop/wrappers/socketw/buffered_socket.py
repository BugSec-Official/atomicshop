"""
``BufferedSocket`` — a thin socket wrapper that "un-reads" bytes the MITM accept
path already consumed back onto the wire.

Why this module exists
----------------------
The sans-io accept path in ``ssl_base.consume_client_hello`` always
*consumes* the first bytes off a just-accepted socket (instead of peeking at
them with ``MSG_PEEK``) so it can parse the TLS ClientHello in Python and
decide whether to speak TLS or fall through to a plain protocol. Consuming
solves two problems with the old peek pair (``is_tls`` + ``peek_alpn_offers``,
both retired):

* A ClientHello that spans multiple TCP segments (common under TLS 1.3 +
  post-quantum key_share, ~1500–2500 B) came back as a short ``MSG_PEEK`` and
  the ALPN parser had to bail. The consumed buffer has no such limit.
* ``MSG_PEEK`` calls don't give stable kernel buffer state between calls, so
  the sniff → header-read → body-read chain had to re-peek every time.

But consuming bytes is a one-way operation: once the kernel hands them to us
we can't push them back for the non-TLS path to re-read. Instead, we wrap the
raw socket in ``BufferedSocket(raw, prefetched)`` and hand *that* downstream.
``recv()`` drains the prefetched bytes first, then switches to the real
socket — so non-TLS protocol parsers (HTTP, MQTT-over-TCP, etc.) see the same
byte stream they would have seen without our interception.

The TLS path handles the same problem differently: it re-injects the same
bytes into an ``ssl.MemoryBIO`` via ``BIOSocketAdapter``. See ``bio_adapter.py``.
"""

import socket
from typing import Optional


class BufferedSocket:
    """
    Socket-like wrapper that replays previously-consumed bytes before falling
    through to a real socket.

    Why this exists
    ---------------
    The MITM accept path consumes the first bytes of every connection to
    classify it as TLS or not. For the non-TLS branch (plain HTTP,
    plaintext MQTT, arbitrary binary) we still need downstream code to see
    those bytes as if they were on the wire. Since the kernel won't let us
    re-inject, we keep them in a Python-side buffer and return them from
    ``recv()`` first, switching to the underlying socket once the buffer
    drains.

    All other socket operations (``sendall``, ``close``, ``getpeername``,
    etc.) pass through to the raw socket unchanged — there's nothing to
    replay on the send side, and FD-level queries must reflect the real
    socket.

    Contract notes
    --------------
    * ``recv(n)`` may return fewer than ``n`` bytes, matching stdlib socket
      semantics. Callers that need exactly N bytes should loop (see
      ``receiver.recv_exact``).
    * A ``recv(0)`` returns ``b''`` without touching the raw socket. This
      is consistent with the stdlib and avoids an off-by-one where a
      zero-length request accidentally consumes buffered bytes.
    * The prefetched buffer is *not* re-issued on subsequent reads once
      drained — this wrapper is single-use for the replay, not a cache.
    """

    def __init__(self, raw_socket: socket.socket, prefetched: bytes):
        """
        :param raw_socket: the underlying TCP socket. All operations other
            than ``recv`` delegate to it. The wrapper does *not* take
            ownership beyond what ``close()`` would delegate — the caller
            is still responsible for lifecycle management if they bypass
            ``close()``.
        :param prefetched: bytes already consumed from ``raw_socket`` (e.g.
            the 3-byte TLS sniff read for a non-TLS peer). These are
            replayed from ``recv()`` before any real ``raw_socket.recv()``
            call. Empty bytes are allowed (degrades to a transparent
            pass-through).
        """
        # ---- Underlying transport ----
        # Kept as a plain attribute (not private) so callers that really
        # need the raw socket can reach it — matches how ``ssl.SSLSocket``
        # exposes itself via ``.socket`` on some paths. We don't advertise
        # it as a stable API though.
        self._raw: socket.socket = raw_socket

        # ---- Replay buffer ----
        # ``memoryview`` would save a copy, but the prefetched blob is tiny
        # (a single TLS record at most, usually just 3 bytes for the
        # non-TLS branch) and ``bytes`` is simpler to reason about when
        # ``recv`` slices it. A ``bytearray`` is used so we can cheaply
        # chop off the front as bytes are delivered.
        self._buffer: bytearray = bytearray(prefetched)

    # ------------------------------------------------------------------
    # recv — the one method that needs replay logic
    # ------------------------------------------------------------------

    def recv(self, bufsize: int, flags: int = 0) -> bytes:
        """
        Read up to ``bufsize`` bytes, preferring the replay buffer.

        Why the logic looks the way it does
        ----------------------------------
        We deliberately *don't* combine a partial buffer drain with a real
        ``recv()`` in a single call. The stdlib contract allows ``recv``
        to return short, and downstream HTTP/MQTT parsers already loop
        over short reads. Concatenating buffer+socket in one call would
        force us to call into the kernel even when the buffer alone
        satisfies the caller — slower, and it would interact badly with
        ``MSG_PEEK`` flags if a caller ever passed one (which parsers
        sometimes do).

        :param bufsize: caller's requested maximum byte count. A value of
            0 returns ``b''`` immediately — matches stdlib semantics and
            avoids surprising buffer consumption.
        :param flags: standard ``recv`` flags (``MSG_PEEK`` etc.). Passed
            through verbatim when we fall through to the raw socket. When
            draining the buffer, ``MSG_PEEK`` is honored by slicing
            without advancing the cursor, so callers can still inspect
            prefetched bytes non-destructively if they want to.
        :return: up to ``bufsize`` bytes. May be shorter if the buffer
            has fewer than ``bufsize`` bytes and the caller should loop.
            Returns ``b''`` on clean EOF from the underlying socket (only
            possible once the buffer is drained).
        """
        # ---- Fast path: caller asked for nothing ----
        # Preserves stdlib behavior; avoids a pointless buffer-manipulation
        # step that could accidentally consume a byte.
        if bufsize <= 0:
            return b''

        # ---- Primary path: replay from the prefetched buffer ----
        # As long as the buffer has *any* bytes, we service the read from
        # it. Short returns are fine — socket callers must already tolerate
        # them, and this keeps the kernel out of the loop while we're
        # replaying.
        if self._buffer:
            # MSG_PEEK support: slice without removing so the prefetched
            # bytes remain visible to a later non-peek call. This is rarely
            # exercised in practice, but matching the kernel's semantics
            # costs almost nothing and avoids a subtle surprise for
            # downstream code that happens to peek.
            if flags & socket.MSG_PEEK:
                return bytes(self._buffer[:bufsize])

            chunk = bytes(self._buffer[:bufsize])
            del self._buffer[:bufsize]
            return chunk

        # ---- Fall-through: buffer drained, delegate to the real socket ----
        return self._raw.recv(bufsize, flags)

    def recv_into(self, buffer, nbytes: int = 0, flags: int = 0) -> int:
        """
        Socket-style ``recv_into`` that respects the replay buffer.

        Why this exists
        ---------------
        Some downstream readers (notably ``socket.makefile()`` when called
        with a buffered mode) call ``recv_into`` instead of ``recv``.
        Without this method the replay buffer would be bypassed and the
        caller would see ``raw`` bytes out of order. Mirrors stdlib
        signature so ``makefile(...)`` keeps working transparently.

        :param buffer: writable buffer (bytearray / memoryview) to fill.
        :param nbytes: max bytes to write; 0 means "fill the buffer".
        :param flags: standard ``recv`` flags, passed through.
        :return: number of bytes written into ``buffer``.
        """
        # ---- Compute effective byte cap ----
        # stdlib treats nbytes=0 as "len(buffer)". We mirror that so
        # ``makefile`` and friends don't have to special-case our wrapper.
        if nbytes == 0:
            nbytes = len(buffer)

        if nbytes <= 0:
            return 0

        # ---- Replay from buffer first ----
        # Same logic as ``recv``: drain the prefetched buffer into the
        # caller's memory, without touching the kernel, as long as any
        # replay bytes remain.
        if self._buffer:
            take = min(nbytes, len(self._buffer))
            mv = memoryview(buffer)
            mv[:take] = self._buffer[:take]
            if not (flags & socket.MSG_PEEK):
                del self._buffer[:take]
            return take

        # ---- Fall-through to the real socket ----
        return self._raw.recv_into(buffer, nbytes, flags)

    # ------------------------------------------------------------------
    # Send side — nothing to replay, pass through verbatim
    # ------------------------------------------------------------------

    def send(self, data, flags: int = 0) -> int:
        """Pass-through to ``raw.send``; there's no replay for the write side."""
        return self._raw.send(data, flags)

    def sendall(self, data, flags: int = 0) -> None:
        """Pass-through to ``raw.sendall``; there's no replay for the write side."""
        return self._raw.sendall(data, flags)

    # ------------------------------------------------------------------
    # Lifecycle & state — always delegate to the real fd
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying socket. Buffer is dropped implicitly."""
        # No explicit buffer clear — the wrapper is about to be GC'd by the
        # caller dropping its reference; and we don't want to *hide* any
        # residual replay bytes if someone peeks into the wrapper after
        # close, since that would mask a bug rather than surface it.
        return self._raw.close()

    def shutdown(self, how: int) -> None:
        return self._raw.shutdown(how)

    def fileno(self) -> int:
        """
        Return the file descriptor of the raw socket.

        Why: ``select.select`` and friends key off fileno(). The wrapper
        must not lie about its FD — the raw socket is what the kernel
        actually sees events on.
        """
        return self._raw.fileno()

    def getpeername(self):
        return self._raw.getpeername()

    def getsockname(self):
        return self._raw.getsockname()

    def getsockopt(self, level: int, optname: int, buflen: Optional[int] = None):
        if buflen is None:
            return self._raw.getsockopt(level, optname)
        return self._raw.getsockopt(level, optname, buflen)

    def setsockopt(self, level: int, optname: int, value) -> None:
        return self._raw.setsockopt(level, optname, value)

    def settimeout(self, timeout) -> None:
        return self._raw.settimeout(timeout)

    def gettimeout(self):
        return self._raw.gettimeout()

    def setblocking(self, flag: bool) -> None:
        return self._raw.setblocking(flag)

    def makefile(self, mode: str = 'r', buffering=None, *, encoding=None, errors=None, newline=None):
        """
        Return a file-like wrapper over this (buffered!) socket.

        Why this exists
        ---------------
        ``socket.makefile()`` is commonly used by HTTP parsers (incl.
        ``http.server``) to iterate request lines. Those parsers read
        through ``recv_into``, so our wrapper's ``recv_into`` replay is
        what gives them the full byte stream including the prefetched
        sniff bytes. Delegates to ``socket.SocketIO`` via the stdlib
        helper — we can't use ``self._raw.makefile`` because that would
        bypass our replay buffer.
        """
        # Reuse the stdlib machinery with ``self`` as the underlying
        # "socket". ``SocketIO`` only requires ``recv_into`` + ``send`` +
        # ``fileno`` + ``close``, all of which we implement.
        return socket.socket.makefile(self, mode, buffering,
                                      encoding=encoding, errors=errors, newline=newline)

    # ------------------------------------------------------------------
    # Introspection helpers for logging / debugging
    # ------------------------------------------------------------------

    @property
    def family(self):
        return self._raw.family

    @property
    def type(self):
        return self._raw.type

    @property
    def proto(self):
        return self._raw.proto

    def __repr__(self) -> str:
        return (
            f"<BufferedSocket raw={self._raw!r} "
            f"prefetched_remaining={len(self._buffer)}>"
        )

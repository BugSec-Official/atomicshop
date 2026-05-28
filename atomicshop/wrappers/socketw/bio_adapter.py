"""
``BIOSocketAdapter`` — SSLSocket-like facade over an ``ssl.SSLObject`` +
``ssl.MemoryBIO`` pair, plumbed onto a raw TCP socket by hand.

Why this module exists
----------------------
The atomicshop MITM accept path consumes the first bytes of every
just-accepted connection (via ``ssl_base.consume_client_hello``) so it can
parse the TLS ClientHello in Python — extract ALPN offers, sniff TLS
version, classify TLS-vs-non-TLS — all *before* OpenSSL is allowed to see
the wire. That consumption is one-way: once we have the bytes in a Python
buffer, the kernel socket's receive buffer has already advanced past them.

Python's stdlib ``ssl`` provides exactly the escape hatch we need:
``SSLContext.wrap_bio(incoming, outgoing)`` returns an ``SSLObject`` that
doesn't touch a socket at all. TLS input goes into ``incoming`` (a
``MemoryBIO``), TLS output comes out of ``outgoing`` (another
``MemoryBIO``). We are responsible for pumping bytes between those BIOs
and the raw socket ourselves.

``BIOSocketAdapter`` is that pump, wrapped in a socket-shaped facade so
downstream code — ``connection_thread_worker``, the SNI callback glue,
the mitm engines — can keep treating it as if it were an ``ssl.SSLSocket``.
We expose the subset of ``SSLSocket`` API that atomicshop actually
exercises (``recv`` / ``sendall`` / ``close`` / ``fileno`` /
``selected_alpn_protocol`` / ``version`` / ``cipher`` / ``getpeername`` /
``getpeercert(binary=True)`` / ``server_hostname`` / ``context``) plus
standard pass-throughs for lifecycle and socket options.

See ``buffered_socket.py`` for the sibling non-TLS wrapper that handles
the same "replay consumed bytes" problem without a TLS handshake.
"""

import ssl
import socket
import time
from typing import Optional


# ----------------------------------------------------------------------
# Tunables
# ----------------------------------------------------------------------

# Chunk size used when we ourselves pull bytes off the raw socket to feed
# ``incoming``. Matches the TLS record ceiling (16384 bytes per record) so
# a single recv can satisfy the largest possible single-record read
# without a second syscall. Smaller would just add loop iterations;
# larger wouldn't help because OpenSSL can't emit more than a record at
# a time anyway.
_RECV_CHUNK: int = 16384

# Bound on the handshake pump loop iterations, to defend against a
# pathological peer that keeps returning ``SSLWantReadError`` but sends
# no useful bytes. Each iteration requires *some* forward progress
# (kernel-side recv or kernel-side send), so a large-but-finite ceiling
# is enough — we're catching pathological loops, not legitimate slow
# handshakes (those are already bounded by socket timeout).
_HANDSHAKE_MAX_ITERATIONS: int = 1024

# Soft deadline for ``close()``'s attempt to send ``close_notify`` via
# ``SSLObject.unwrap()``. Peer misbehavior during shutdown must not
# block the worker thread.
_UNWRAP_DEADLINE_SECONDS: float = 1.0


class BIOSocketAdapter:
    """
    ``ssl.SSLSocket``-shaped wrapper around an ``SSLObject`` + two
    ``MemoryBIO`` instances + a raw TCP socket.

    Why this exists
    ---------------
    The MITM accept path must read + parse the ClientHello before the
    real TLS handshake runs. Once those bytes are in a Python buffer the
    only way to hand them back to OpenSSL is via ``MemoryBIO.write()`` →
    ``SSLContext.wrap_bio()``. That API returns an ``SSLObject``, which
    has no socket affinity; code that expects an ``SSLSocket`` (our
    engine pipeline, the SNI callback, the recorder) would otherwise
    need a large rewrite. This adapter bridges the two — the downstream
    code sees a socket-shaped object and never has to learn about BIOs.

    What this adapter is *not*
    --------------------------
    * Not a generic async wrapper. Every operation is blocking on
      ``raw``'s timeout.
    * Not a complete ``SSLSocket`` reimplementation. We only implement
      the methods atomicshop actually calls. If a new call path is added
      and hits an ``AttributeError`` on this class, add the method here
      (usually a one-liner that proxies to ``_ssl_object`` or ``_raw``).
    """

    def __init__(
            self,
            raw_socket: socket.socket,
            ssl_object: ssl.SSLObject,
            incoming: ssl.MemoryBIO,
            outgoing: ssl.MemoryBIO
    ):
        """
        :param raw_socket: the underlying TCP socket. We read ciphertext
            from it and write ciphertext to it on behalf of OpenSSL.
            Lifecycle: ``close()`` on this adapter closes the raw socket.
        :param ssl_object: an ``ssl.SSLObject`` built from
            ``SSLContext.wrap_bio(incoming, outgoing, server_side=True)``.
            Must have completed the handshake (or at least had enough
            data pumped through ``incoming`` that the handshake can
            complete lazily) before ``recv`` / ``sendall`` are called —
            in practice the caller has already run ``_pump_handshake``
            in ``creator.wrap_bio_server_with_error_message``.
        :param incoming: the ``MemoryBIO`` feeding ciphertext *into*
            OpenSSL. The adapter's ``recv`` pumps raw socket reads here.
        :param outgoing: the ``MemoryBIO`` receiving ciphertext *out of*
            OpenSSL. The adapter's ``sendall`` / ``_flush_outgoing``
            drain it to the raw socket.
        """
        # ---- Core objects ----
        # Store everything as plain attributes (no underscores on the
        # SSL-related state). Downstream code that needs access for
        # logging or SNI can reach them; the socket-style facade methods
        # are just a convenience layer on top.
        self._raw: socket.socket = raw_socket
        self._ssl_object: ssl.SSLObject = ssl_object
        self._incoming: ssl.MemoryBIO = incoming
        self._outgoing: ssl.MemoryBIO = outgoing

        # ---- Close latch ----
        # ``close()`` must be idempotent: thread-worker teardown can
        # call it multiple times on the same object. Flag it so we don't
        # try to write a second close_notify after the socket is already
        # gone.
        self._closed: bool = False

    # ------------------------------------------------------------------
    # Pump primitives — the only place we touch the raw socket for TLS
    # ------------------------------------------------------------------

    def _flush_outgoing(self) -> None:
        """
        Drain every byte currently in ``outgoing`` to ``raw``.

        Why this exists
        ---------------
        OpenSSL writes ciphertext into ``outgoing`` whenever it has
        something to say — during the handshake, in response to a
        ``write`` call, after a renegotiation. ``outgoing`` is just a
        buffer; nothing moves those bytes to the wire unless we do it
        explicitly. Every path that might have produced output — pre-
        ``recv``, post-``write``, mid-``close`` — must call this to
        avoid silently stalling the peer.

        ``outgoing.read()`` with no argument drains the whole buffer in
        one call, so we only need to loop until ``pending`` reports
        zero.
        """
        while self._outgoing.pending:
            chunk = self._outgoing.read()
            if not chunk:
                # Defensive: .pending said nonzero but .read() returned
                # empty. Shouldn't happen under normal MemoryBIO use,
                # but bail rather than loop forever if it does.
                break
            self._raw.sendall(chunk)

    def _feed_incoming_from_raw(self) -> bool:
        """
        Read ciphertext from ``raw`` and push it into ``incoming``.

        :return: ``True`` if at least one byte was read, ``False`` on a
            clean EOF (peer closed before we got more ciphertext).

        Why this returns a bool
        -----------------------
        The ``recv`` / handshake loops need to distinguish "no progress,
        go around again" (caller loops) from "peer is gone" (caller
        bails to an empty string / exception). Raising on EOF here
        would force callers to wrap every call in try/except; a bool
        lets them branch inline.
        """
        data = self._raw.recv(_RECV_CHUNK)
        if not data:
            # Clean EOF. Still write a zero-length marker into
            # incoming's EOF side so OpenSSL can react appropriately
            # (SSLEOFError vs hang). write_eof is only safe once — we
            # rely on the caller not calling this again after False.
            self._incoming.write_eof()
            return False
        self._incoming.write(data)
        return True

    # ------------------------------------------------------------------
    # The core I/O methods — what downstream code actually calls
    # ------------------------------------------------------------------

    def recv(self, bufsize: int, flags: int = 0) -> bytes:
        """
        Read up to ``bufsize`` bytes of plaintext from the TLS stream.

        Why the loop exists
        -------------------
        ``SSLObject.read()`` can raise ``SSLWantReadError`` when it
        needs more ciphertext in ``incoming`` before it can produce a
        plaintext byte — e.g. the decrypted record isn't complete yet.
        That's our cue to pump more ciphertext from the raw socket.
        ``SSLWantWriteError`` is also possible mid-stream (rare server
        renegotiation), in which case we drain ``outgoing`` and try
        again.

        :param bufsize: maximum plaintext bytes to return. A short
            return is allowed, matching ``ssl.SSLSocket.recv``.
        :param flags: accepted for signature compatibility with
            ``socket.socket.recv``; ``MSG_PEEK`` is *not* supported over
            a TLS stream (OpenSSL has no equivalent) and any flag bits
            will be silently ignored, same as stdlib ``SSLSocket``.
        :return: up to ``bufsize`` plaintext bytes, or ``b''`` on clean
            TLS close_notify from the peer.
        """
        _ = flags  # Explicit unused-marker; signature kept for
                   # SSLSocket duck-typing compatibility.

        while True:
            try:
                return self._ssl_object.read(bufsize)
            except ssl.SSLWantReadError:
                # ---- Need more ciphertext in incoming ----
                # Push outbound first in case the handshake state
                # machine is mid-renegotiation and needs a write too
                # (cheap; no-op if outgoing is empty).
                self._flush_outgoing()
                if not self._feed_incoming_from_raw():
                    # Peer closed before a full record arrived. The
                    # next .read() will raise SSLEOFError or return
                    # b'', which is the right signal upstream.
                    return b''
            except ssl.SSLWantWriteError:
                # ---- Need to flush ciphertext before we can read ----
                # This is unusual on the read path but legal — e.g. a
                # server-initiated rehandshake queues output during
                # what the caller thinks is a pure read.
                self._flush_outgoing()
            except ssl.SSLZeroReturnError:
                # Peer sent close_notify cleanly. Mirror stdlib's
                # ``SSLSocket.recv``: return empty bytes.
                return b''

    def recv_into(self, buffer, nbytes: int = 0, flags: int = 0) -> int:
        """
        ``recv_into`` equivalent for callers that use ``makefile()``.

        Why: ``socket.SocketIO`` (used by ``makefile``) calls
        ``recv_into`` on its underlying socket. If we only provided
        ``recv`` the file-like path would AttributeError. Simple wrapper
        on top of ``recv``.
        """
        _ = flags
        if nbytes == 0:
            nbytes = len(buffer)
        if nbytes <= 0:
            return 0
        data = self.recv(nbytes)
        if not data:
            return 0
        memoryview(buffer)[:len(data)] = data
        return len(data)

    def send(self, data, flags: int = 0) -> int:
        """
        Send plaintext over the TLS stream. Returns the number of
        plaintext bytes accepted by OpenSSL (not ciphertext bytes on
        the wire).

        Why this has its own loop
        -------------------------
        ``SSLObject.write()`` can raise ``SSLWantWriteError`` if the
        outgoing BIO is already at its internal limit (practically
        never — ``MemoryBIO`` is unbounded — but we handle it for
        completeness). Also pumps outgoing post-write so the ciphertext
        doesn't linger in the BIO.
        """
        _ = flags
        while True:
            try:
                written = self._ssl_object.write(data)
                self._flush_outgoing()
                return written
            except ssl.SSLWantWriteError:
                self._flush_outgoing()
            except ssl.SSLWantReadError:
                # Mid-renegotiation: need to read ciphertext from peer
                # before our write can continue. Pump and retry.
                self._flush_outgoing()
                if not self._feed_incoming_from_raw():
                    # Peer disappeared mid-renegotiation. Nothing else
                    # we can do; surface as a broken pipe.
                    raise ConnectionError(
                        "BIOSocketAdapter.send: peer closed during renegotiation")

    def sendall(self, data, flags: int = 0) -> None:
        """
        Send every byte of ``data``, looping over partial ``send``
        returns.

        Why: ``ssl.SSLSocket.sendall`` provides this semantic and
        downstream code relies on it (e.g. HTTP response serialization).
        OpenSSL's ``write`` is allowed to accept fewer bytes than
        offered, especially on large buffers.
        """
        _ = flags
        offset = 0
        mv = memoryview(data)
        while offset < len(mv):
            written = self.send(mv[offset:])
            if written <= 0:
                raise ConnectionError(
                    f"BIOSocketAdapter.sendall: write returned {written} "
                    f"after {offset}/{len(mv)} bytes")
            offset += written

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """
        Close the TLS stream and the underlying socket.

        Why the tri-phase close
        -----------------------
        Proper TLS shutdown sends a ``close_notify`` alert. If we just
        close the raw socket the peer sees a truncation attack and may
        log it as an error — cosmetic, but noisy. Sequence:

        1. Best-effort ``unwrap()`` to drive close_notify into
           ``outgoing``. Bounded by ``_UNWRAP_DEADLINE_SECONDS`` because
           a slow peer can keep returning ``SSLWantReadError`` forever.
        2. Drain ``outgoing`` to the wire so the close_notify actually
           reaches the peer.
        3. Close the raw socket.

        Any exception in steps 1-2 is swallowed: we're tearing down,
        and a raised exception in ``close()`` masks the real error
        that triggered the teardown.
        """
        # ---- Idempotence guard ----
        # Worker shutdown paths may call close twice (engine teardown +
        # finally block). Make the second call a no-op so we don't
        # attempt a second write on a closed fd.
        if self._closed:
            return
        self._closed = True

        # ---- Phase 1: attempt close_notify via unwrap, bounded ----
        deadline = time.monotonic() + _UNWRAP_DEADLINE_SECONDS
        try:
            while True:
                try:
                    self._ssl_object.unwrap()
                    break
                except ssl.SSLWantReadError:
                    self._flush_outgoing()
                    if time.monotonic() >= deadline:
                        break
                    # Give the peer a moment to reply with its own
                    # close_notify; if it never does we exit on the
                    # next deadline check.
                    try:
                        if not self._feed_incoming_from_raw():
                            break
                    except OSError:
                        break
                except ssl.SSLWantWriteError:
                    self._flush_outgoing()
                    if time.monotonic() >= deadline:
                        break
        except (ssl.SSLError, OSError, ValueError):
            # ValueError comes up if the ssl_object was never fully
            # handshaken. All of these are "we tried, give up".
            pass

        # ---- Phase 2: flush any remaining ciphertext ----
        try:
            self._flush_outgoing()
        except OSError:
            pass

        # ---- Phase 3: always close the real socket ----
        # This is the only step that *must* succeed; do it last so the
        # FD is released no matter what the TLS layer did.
        try:
            self._raw.close()
        except OSError:
            pass

    def shutdown(self, how: int) -> None:
        """Shut down the underlying socket in the requested direction.

        Does not attempt a TLS ``close_notify`` — callers that want a
        clean TLS shutdown should call ``close()`` instead. Matches
        stdlib ``SSLSocket.shutdown`` semantics.
        """
        self._raw.shutdown(how)

    # ------------------------------------------------------------------
    # FD / addressing pass-throughs
    # ------------------------------------------------------------------

    def fileno(self) -> int:
        """
        File descriptor of the underlying socket.

        Why: used by ``select.select`` and by
        ``receiver.is_socket_ready_for_read`` to check pending data.
        (Caveat: this only reflects kernel-side ciphertext, not any
        decrypted plaintext already sitting in OpenSSL's internal
        buffers. Pre-existing limitation also present on ``SSLSocket``.)
        """
        if self._closed:
            return -1
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

    @property
    def family(self):
        return self._raw.family

    @property
    def type(self):
        return self._raw.type

    @property
    def proto(self):
        return self._raw.proto

    # ------------------------------------------------------------------
    # TLS-level accessors — proxy to the SSLObject
    # ------------------------------------------------------------------

    def version(self) -> Optional[str]:
        """
        Negotiated TLS protocol version string (e.g. ``"TLSv1.3"``), or
        ``None`` if the handshake hasn't completed. Mirrors
        ``ssl.SSLSocket.version``; used by the accept-flow logger to
        report the *real* version (the record-layer sniff in
        ``consume_client_hello`` can't distinguish 1.2 from 1.3).
        """
        return self._ssl_object.version()

    def cipher(self):
        """
        Tuple of ``(cipher_name, tls_version, secret_bits)`` or
        ``None``. Direct proxy to ``SSLObject.cipher()``.
        """
        return self._ssl_object.cipher()

    def selected_alpn_protocol(self) -> Optional[str]:
        """
        Protocol selected by the ALPN negotiation on this leg, or
        ``None`` if no ALPN was negotiated. The MITM engine pipeline
        uses this to decide whether to treat the session as HTTP/2 vs
        HTTP/1.1 vs MQTT etc., so it must reflect the inbound leg's
        actual selection — not the client's offer list.
        """
        return self._ssl_object.selected_alpn_protocol()

    def getpeercert(self, binary_form: bool = False):
        """
        Peer (client) certificate if one was requested and presented.

        Why: atomicshop's mTLS subdomain flow calls
        ``getpeercert(True)`` on the inbound leg to capture the client
        cert. Directly proxies the ``SSLObject`` call; ``binary_form``
        is forwarded unchanged.
        """
        return self._ssl_object.getpeercert(binary_form)

    def pending(self) -> int:
        """
        Plaintext bytes already decrypted inside OpenSSL's internal
        buffer. ``select.select`` on the raw FD doesn't see these, so a
        naive readiness check can miss a full record. Currently unused
        by the accept path but exposed for parity with
        ``ssl.SSLSocket.pending`` in case we later fix the
        "SSL-buffered plaintext" select gap (see
        ``socket_wrapper.py`` Risk #1 in the refactor plan).
        """
        return self._ssl_object.pending()

    # ------------------------------------------------------------------
    # SSLObject-proxied properties — must be read/write, not just read
    # ------------------------------------------------------------------

    @property
    def server_hostname(self) -> Optional[str]:
        """
        The SNI server_name extension value the peer sent, or ``None``.
        Read-only: ``ssl.SSLObject.server_hostname`` is a read-only property
        set by Python's TLS stack from the ClientHello SNI extension.
        """
        return self._ssl_object.server_hostname

    @property
    def context(self) -> ssl.SSLContext:
        """
        The ``SSLContext`` currently driving this connection. The SNI
        handler swaps this mid-handshake (``sni.py:352``) when a new
        domain-specific certificate must be loaded, so the setter must
        delegate.
        """
        return self._ssl_object.context

    @context.setter
    def context(self, new_context: ssl.SSLContext) -> None:
        self._ssl_object.context = new_context

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        try:
            version = self._ssl_object.version()
        except Exception:
            version = "?"
        return (
            f"<BIOSocketAdapter raw={self._raw!r} "
            f"version={version} closed={self._closed}>"
        )

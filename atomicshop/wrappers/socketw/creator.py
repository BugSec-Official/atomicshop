import os
import socket
import ssl
import time

from . import socket_base, bio_adapter
from ...print_api import print_api


# Default overall handshake deadline for the BIO-pumped wrap path. Matches
# the 10 s used by the legacy ``wrap_socket`` accept path before the
# consume+MemoryBIO refactor, so timing behavior is unchanged.
_BIO_HANDSHAKE_DEADLINE_SECONDS: float = 10.0

# Chunk size when pumping ciphertext from the raw socket into ``incoming``
# during the handshake. 16384 is the TLS record ceiling, so a single recv
# is guaranteed sufficient for a single record.
_BIO_HANDSHAKE_RECV_CHUNK: int = 16384


def create_socket_ipv4_tcp():
    # When using 'with' statement, no need to use "socket.close()" method to disconnect when finished
    # AF_INET - Socket family of IPv4
    # SOCK_STREAM - Socket type of TCP
    return socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def add_reusable_address_option(socket_instance):
    # "setsockopt" is a method that can add options to the socket. Not needed for regular connection,
    # but for some types of protocols that come after that.
    # SOL_SOCKET - the "level", constant that contains the "SP_REUSEADDR"
    # SO_REUSEADDR - permit reuse of local addresses for this socket. If you enable this option, you can actually
    # have two sockets with the same Internet port number. Needed for protocols that force you to use the same port.
    # 1 - Sets this to true
    # For more options of this constant:
    # https://www.gnu.org/software/libc/manual/html_node/Socket_002dLevel-Options.html#Socket_002dLevel-Options
    socket_instance.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


def create_ssl_context_for_server(
        enable_sslkeylogfile_env_to_client_ssl_context: bool = False,
        sslkeylog_file_path: str = None,
        allow_legacy: bool = False,
        alpn_protocols: list[str] | None = None
) -> ssl.SSLContext:
    """
    This function creates the SSL context for the server.
    Meaning that your script will act like a server, and the client will connect to it.
    """
    # Creating context with SSL certificate and the private key before the socket
    # https://docs.python.org/3/library/ssl.html
    # Creating context for SSL wrapper, specifying "PROTOCOL_TLS_SERVER" will pick the best TLS version protocol for
    # the server.

    # ssl_context: ssl.SSLContext = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)

    # # Enforce the use of TLS 1.2 only (disable TLS 1.0, TLS 1.1, and TLS 1.3)
    # ssl_context.options |= ssl.OP_NO_TLSv1           # Disable TLS 1.0
    # ssl_context.options |= ssl.OP_NO_TLSv1_1         # Disable TLS 1.1
    # ssl_context.options |= ssl.OP_NO_TLSv1_3         # Disable TLS 1.3

    # Correct factory for servers
    ssl_context: ssl.SSLContext = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    # Modern default; relax only if you must
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

    # Don't verify client certificates.
    ssl_context.verify_mode = ssl.CERT_NONE
    ssl_context.check_hostname = False

    if enable_sslkeylogfile_env_to_client_ssl_context:
        if sslkeylog_file_path is None:
            sslkeylog_file_path = os.environ.get('SSLKEYLOGFILE')

        if not os.path.exists(sslkeylog_file_path):
            open(sslkeylog_file_path, "a").close()

        ssl_context.keylog_filename = sslkeylog_file_path

    # If you must support old clients that only offer TLS_RSA_* suites under OpenSSL 3:
    if allow_legacy:
        # This enables RSA key exchange and other legacy bits at security level 1
        ssl_context.set_ciphers('DEFAULT:@SECLEVEL=1')
        # If you truly have TLS 1.0/1.1 clients, uncomment the next line (not recommended):
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1

    # Mirror caller-supplied ALPN. None / empty list = don't advertise ALPN.
    if alpn_protocols:
        ssl_context.set_alpn_protocols(alpn_protocols)

    return ssl_context


def create_ssl_context_for_client(
        enable_sslkeylogfile_env_to_client_ssl_context: bool = False,
        sslkeylog_file_path: str = None,
        alpn_protocols: list[str] | None = None
) -> ssl.SSLContext:
    """
    This function creates the SSL context for the client.
    This means that your script will act like a client, and will connect to a server.
    The SSL context is created with the "PROTOCOL_TLS_CLIENT" protocol.

    :param enable_sslkeylogfile_env_to_client_ssl_context: boolean, enables the SSLKEYLOGFILE environment variable
        to the SSL context. Default is False.
        if True, SSLKEYLOGFILE will be added to SSL context with:
        ssl_context.keylog_filename = os.environ.get('SSLKEYLOGFILE')
        This is useful for debugging SSL/TLS connections with WireShark.
        Since WireShark also uses this environment variable to read the key log file and apply to the SSL/TLS
        connections, so you can see the decrypted traffic.
    :param sslkeylog_file_path: string, full file path for the SSL key log file. Default is None.

    :return: ssl.SSLContext
    """
    ssl_context: ssl.SSLContext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    if enable_sslkeylogfile_env_to_client_ssl_context:
        if sslkeylog_file_path is None:
            sslkeylog_file_path = os.environ.get('SSLKEYLOGFILE')

        if not os.path.exists(sslkeylog_file_path):
            open(sslkeylog_file_path, "a").close()

        ssl_context.keylog_filename = sslkeylog_file_path

    current_ciphers = 'AES256-GCM-SHA384:' + ssl._DEFAULT_CIPHERS
    ssl_context.set_ciphers(current_ciphers)

    # Mirror caller-supplied ALPN. None / empty list = don't advertise ALPN.
    if alpn_protocols:
        ssl_context.set_alpn_protocols(alpn_protocols)

    return ssl_context


def set_client_ssl_context_ca_default_certs(ssl_context):
    """
    "load_default_certs" method is telling the client to check the local certificate storage on the system for the
    needed certificate of the server. Without this line you will get an error from the server that the client
    is using self-signed certificate. Which is partly true, since you used the SLL wrapper,
    but didn't specify the certificate at all.
    -----------------------------------------
    https://docs.python.org/3/library/ssl.html#ssl.SSLContext.load_default_certs
    Load a set of default “certification authority” (CA) certificates from default locations.
    On Windows it loads CA certs from the CA and ROOT system stores.
    On all systems it calls SSLContext.set_default_verify_paths().
    In the future the method may load CA certificates from other locations, too.

    The purpose flag specifies what kind of CA certificates are loaded.
    The default settings Purpose.SERVER_AUTH loads certificates, that are flagged and trusted for
    TLS web server authentication (client side sockets). Purpose.CLIENT_AUTH loads CA certificates for
    client certificate verification on the server side.
    -----------------------------------------
    """

    # The purpose of the certificate is to authenticate on the server
    # context.load_default_certs(Purpose.SERVER_AUTH)
    # You don't have to specify the purpose to connect, but if you get a purpose error, you know where to find it
    ssl_context.load_default_certs()


def set_client_ssl_context_certificate_verification_ignore(ssl_context):
    # If we want to ignore bad server certificates when connecting as a client, we need to think about security.
    # If you care, you should not need to do it, for MITM possibilities.
    # To do this anyway we need first to disable 'check_hostname' and only
    # then set 'verify_mode' to 'ssl.CERT_NONE'. If we do it in backwards order, when 'verify_mode' comes before
    # 'check_hostname' then we'll get an exception that 'check_hostname' needs to be False.
    # This setting should eliminate ssl error on 'SSLSocket.connect()':
    # ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED]
    # certificate verify failed: unable to get local issuer certificate (_ssl.c:997)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE


def load_certificate_and_key_into_server_ssl_context(
        ssl_context,
        certificate_file_path: str,
        key_file_path: str = None,
        print_kwargs: dict = None
):
    """

    :param ssl_context:
    :param certificate_file_path:
    :param key_file_path: string, full file path for the key file. If the certificate contains both the key and the
        certificate in one file, "keyfile" parameter can be None. Default is None.
    :param print_kwargs: dictionary, keyword arguments for 'print_api' function.
    :return:
    """

    # If the certificate contains both the key and the certificate in one file,
    # "keyfile" parameter can be "None".
    try:
        ssl_context.load_cert_chain(certfile=certificate_file_path, keyfile=key_file_path)
    except ssl.SSLError as exception_object:
        if 'PEM' in str(exception_object):
            message = \
                f'Custom Certificate Problem with either certificate or key.\n' \
                f'Make sure that both are in ".PEM" format\n' \
                f"Or your certificate contains the key if you didn't specify it.\n" \
                f'{exception_object}'
            print_api(message, error_type=True, logger_method="critical", **print_kwargs)


def copy_server_ctx_settings(src: ssl.SSLContext, dst: ssl.SSLContext) -> None:
    # Versions & options
    try: dst.minimum_version = src.minimum_version
    except Exception: pass
    try: dst.maximum_version = src.maximum_version
    except Exception: pass
    try: dst.options = src.options
    except Exception: pass

    # Verification knobs (server usually CERT_NONE unless you do mTLS)
    try: dst.verify_mode = src.verify_mode
    except Exception: pass
    try: dst.check_hostname = src.check_hostname
    except Exception: pass

    # Cipher policy – replicate current enabled list
    try:
        cipher_names = ':'.join(c['name'] for c in src.get_ciphers())
        if cipher_names:
            dst.set_ciphers(cipher_names)
    except Exception:
        pass

    # (ALPN/curves/etc. don’t have public getters; set them the same way you set them on src, if applicable)


def create_server_ssl_context___load_certificate_and_key(
        certificate_file_path: str,
        key_file_path: str | None,
        inherit_from: ssl.SSLContext | None = None,
        enable_sslkeylogfile_env_to_client_ssl_context: bool = False,
        sslkeylog_file_path: str = None,
        alpn_protocols: list[str] | None = None,
) -> ssl.SSLContext:
    # Create and set ssl context for server.
    ssl_context: ssl.SSLContext = create_ssl_context_for_server(
        allow_legacy=True, enable_sslkeylogfile_env_to_client_ssl_context=enable_sslkeylogfile_env_to_client_ssl_context,
        sslkeylog_file_path=sslkeylog_file_path, alpn_protocols=alpn_protocols)

    # If you replaced contexts during SNI, copy policy from the old one
    if inherit_from is not None:
        copy_server_ctx_settings(inherit_from, ssl_context)

    # Load certificate into context.
    load_certificate_and_key_into_server_ssl_context(ssl_context, certificate_file_path, key_file_path)
    # Return ssl context only.
    return ssl_context


def _pump_handshake(
        raw_socket: socket.socket,
        ssl_object: ssl.SSLObject,
        incoming: ssl.MemoryBIO,
        outgoing: ssl.MemoryBIO,
        deadline_seconds: float = _BIO_HANDSHAKE_DEADLINE_SECONDS
) -> None:
    """
    Drive an ``SSLObject`` through its handshake by pumping bytes between
    the two ``MemoryBIO`` instances and a raw TCP socket.

    Why this exists
    ---------------
    Unlike ``SSLSocket.wrap_socket()`` (which owns a socket fd and runs
    the handshake itself transparently), ``SSLContext.wrap_bio()`` hands
    back an ``ssl.SSLObject`` that has no socket affinity. It can't read
    or write on its own — it tells *us* what it needs via
    ``SSLWantReadError`` / ``SSLWantWriteError`` and we shuttle bytes
    between the BIOs and the real socket until the handshake completes.

    The accept path uses ``wrap_bio`` (not ``wrap_socket``) because the
    ClientHello has already been consumed into a Python buffer by
    ``ssl_base.consume_client_hello`` and re-injected into ``incoming``.
    OpenSSL can only meet that injection if we drive it manually.

    :param raw_socket: the already-accepted TCP socket that the peer is
        communicating on. We read ciphertext from it and write ciphertext
        to it on behalf of OpenSSL.
    :param ssl_object: ``SSLObject`` produced by
        ``ssl_context.wrap_bio(incoming, outgoing, server_side=True)``.
        Must have had the ClientHello (from
        ``ssl_base.consume_client_hello``) already written to
        ``incoming`` before this function is called, or else the
        handshake will deadlock on the first ``SSLWantReadError``.
    :param incoming: ``MemoryBIO`` that OpenSSL reads ciphertext from.
    :param outgoing: ``MemoryBIO`` that OpenSSL writes ciphertext to.
    :param deadline_seconds: overall handshake deadline. Once exceeded,
        we raise ``TimeoutError`` regardless of which direction is
        pending. This prevents a malicious or slow peer from holding a
        worker thread forever on a stuck handshake.

    :raises TimeoutError: if the handshake hasn't completed by
        ``deadline_seconds``.
    :raises ssl.SSLError: any real TLS protocol error from OpenSSL
        (bad_record_mac, handshake_failure, etc.). Caller catches this.
    :raises ConnectionError: peer closed the socket before the handshake
        could complete.
    """

    # ---- Compute absolute deadline once ----
    # ``time.monotonic()`` is the right clock here — immune to wall-clock
    # adjustments — and we convert the relative deadline to an absolute
    # one so the per-loop comparison is a single subtraction.
    deadline = time.monotonic() + deadline_seconds

    # ---- Enforce the deadline at the socket layer too ----
    # We also set the socket's own timeout, so a blocked recv() can't
    # block past the deadline even if OpenSSL keeps asking for more.
    # Save/restore to avoid mutating caller-visible state.
    prior_timeout = raw_socket.gettimeout()
    raw_socket.settimeout(deadline_seconds)

    try:
        # ---- Main pump loop ----
        # Each iteration does one of three things and loops:
        #   * handshake completes -> return
        #   * SSLWantReadError -> drain outgoing to wire (in case we
        #     owe the peer something), then read more ciphertext in.
        #   * SSLWantWriteError -> drain outgoing to wire; no read.
        while True:
            # ---- Hard timeout check every iteration ----
            # Catches the pathological case where OpenSSL oscillates
            # between want-read and want-write without real progress.
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"_pump_handshake: TLS handshake exceeded "
                    f"{deadline_seconds}s deadline")

            try:
                ssl_object.do_handshake()
                # ---- Success: drain any final ciphertext ----
                # OpenSSL may have queued a last record (ServerFinished
                # under TLS 1.2, or NewSessionTicket under TLS 1.3)
                # into outgoing just before returning. If we don't flush
                # it the peer never sees it and the first real recv()
                # will hang.
                while outgoing.pending:
                    raw_socket.sendall(outgoing.read())
                return
            except ssl.SSLWantReadError:
                # ---- Flush any pending write first ----
                # In TLS 1.3 the server's first flight (EE / CERT /
                # CERT_VERIFY / FINISHED) is written into outgoing while
                # the state machine is simultaneously waiting for the
                # client's FINISHED. If we only pumped reads we'd
                # deadlock; the peer can't send its reply until it sees
                # our bytes on the wire.
                while outgoing.pending:
                    raw_socket.sendall(outgoing.read())

                # ---- Now read more ciphertext into incoming ----
                try:
                    chunk = raw_socket.recv(_BIO_HANDSHAKE_RECV_CHUNK)
                except socket.timeout:
                    # Normalize to stdlib TimeoutError so callers can
                    # use a single except clause.
                    raise TimeoutError(
                        f"_pump_handshake: recv timed out during handshake")

                if not chunk:
                    # Clean EOF mid-handshake is not recoverable.
                    raise ConnectionError(
                        "_pump_handshake: peer closed during TLS handshake")
                incoming.write(chunk)
            except ssl.SSLWantWriteError:
                # ---- Outgoing BIO full (practically: never) ----
                # ``MemoryBIO`` is unbounded, so this branch mostly
                # exists for symmetry. Drain what we have and retry.
                while outgoing.pending:
                    raw_socket.sendall(outgoing.read())
    finally:
        # ---- Restore caller's socket timeout ----
        # The accept path may rely on a different timeout for the
        # steady-state I/O phase. Make sure our handshake-only deadline
        # doesn't leak out.
        raw_socket.settimeout(prior_timeout)


def wrap_bio_server_with_error_message(
        raw_socket: socket.socket,
        ssl_context: ssl.SSLContext,
        prefetched: bytes,
        domain_from_dns_server: str = None,
        print_kwargs: dict = None,
        deadline_seconds: float = _BIO_HANDSHAKE_DEADLINE_SECONDS
):
    """
    Sans-io server TLS wrap: re-inject an already-consumed ClientHello
    into a ``MemoryBIO``, pump the handshake, return a
    ``BIOSocketAdapter`` that downstream code can use as if it were an
    ``ssl.SSLSocket``.

    Why this exists (the whole point of the refactor)
    -------------------------------------------------
    The old accept path called ``SSLContext.wrap_socket(raw)`` and let
    OpenSSL read the ClientHello off the kernel socket directly. That
    meant the ClientHello was invisible to Python — we couldn't parse
    the ALPN offers, sniff the version, or even decide TLS-vs-not
    *before* committing to a full ``wrap_socket`` call. Our workaround
    was ``MSG_PEEK`` on the raw socket (``is_tls`` + ``peek_alpn_offers``,
    now retired), which broke whenever the ClientHello spanned multiple
    TCP segments.

    The sans-io pattern reverses the ownership: Python reads the
    ClientHello bytes (``ssl_base.consume_client_hello``), parses them,
    then hands them back to OpenSSL via a ``MemoryBIO``. OpenSSL runs
    the real handshake against the re-injected bytes; we get faithful
    ALPN/version/SNI information out of the pre-parse *and* a working
    TLS session. Same general approach used by other L7 TLS proxies.

    :param raw_socket: the just-accepted TCP socket.
    :param ssl_context: the server ``SSLContext`` (already configured
        with certs, SNI callback, ALPN protocols, etc.) — produced by
        ``SNISetup.wrap_socket_with_ssl_context_server_sni_extended``.
    :param prefetched: the bytes we already consumed off the socket to
        sniff/parse the ClientHello. Must include at least the full
        ClientHello record — if it doesn't, OpenSSL will ask for more
        via ``SSLWantReadError`` and the pump will satisfy it from the
        real socket, but the extra hop is unnecessary.
    :param domain_from_dns_server: accepted for signature parity with the
        accept-path helpers; not used structurally.
    :param print_kwargs: forwarded to ``print_api`` for error logging.
    :param deadline_seconds: overall handshake deadline; matches the
        10 s default of the legacy accept path.

    :return: ``(BIOSocketAdapter | None, error_message | None)``.
        On success the adapter is returned and error_message is None.
        On handshake failure the adapter is None and error_message
        contains a short human-readable reason, so callers branch on a
        plain return value instead of catching exceptions.
    """

    _ = domain_from_dns_server  # Kept for signature parity; not used.

    # ---- Build the BIO pair + SSLObject ----
    # ``MemoryBIO`` instances are one-way: ``incoming`` is the pipe
    # *into* OpenSSL, ``outgoing`` is the pipe *out of* OpenSSL. The
    # SSLObject doesn't own the BIOs; we write/read on them directly.
    incoming = ssl.MemoryBIO()
    outgoing = ssl.MemoryBIO()
    ssl_object = ssl_context.wrap_bio(incoming, outgoing, server_side=True)

    # ---- Re-inject the consumed ClientHello ----
    # This is the whole reason for the wrap_bio detour. The bytes in
    # ``prefetched`` came off the same socket we're now about to read
    # from (``raw_socket``), so to OpenSSL it looks identical to having
    # read them itself.
    if prefetched:
        incoming.write(prefetched)

    # ---- Drive the handshake ----
    # Any protocol-level failure (cert problem, alert, bad_record_mac,
    # etc.) is reported as an ``SSLError`` whose string we pass back to
    # the caller. ``OSError`` covers socket-level failures during the
    # pump. ``TimeoutError`` covers our own deadline enforcement.
    try:
        _pump_handshake(raw_socket, ssl_object, incoming, outgoing,
                        deadline_seconds=deadline_seconds)
    except ssl.SSLError as exc:
        error_message = f"TLS handshake failed (SSL error): {exc}"
        print_api(error_message, error_type=True, logger_method="error",
                  **(print_kwargs or {}))
        return None, error_message
    except TimeoutError as exc:
        error_message = f"TLS handshake timed out: {exc}"
        print_api(error_message, error_type=True, logger_method="error",
                  **(print_kwargs or {}))
        return None, error_message
    except (ConnectionError, OSError) as exc:
        error_message = f"TLS handshake failed (socket error): {exc}"
        print_api(error_message, error_type=True, logger_method="error",
                  **(print_kwargs or {}))
        return None, error_message

    # ---- Wrap everything in an SSLSocket-shaped facade ----
    # The downstream pipeline ( connection_thread_worker, engines,
    # recorders) expects SSLSocket duck-typing. See ``bio_adapter.py``
    # for the implemented surface.
    adapter = bio_adapter.BIOSocketAdapter(
        raw_socket=raw_socket,
        ssl_object=ssl_object,
        incoming=incoming,
        outgoing=outgoing,
    )
    return adapter, None


def wrap_socket_with_ssl_context_client(socket_object, ssl_context, server_hostname: str = None):
    # Wrapping the socket with "ssl.SSLContext" object to make "ssl.SSLSocket" object.
    # With "server_hostname" you don't have to use DNS hostname, you can use the IP, just remember to add
    # the address to your Certificate under "X509v3 Subject Alternative Name"
    # SSL wrapping should happen after socket creation and before connection:
    # https://docs.python.org/3/library/ssl.html
    return ssl_context.wrap_socket(sock=socket_object, server_side=False, server_hostname=server_hostname)


def bind_socket_with_ip_port(socket_object, ip_address: str, port: int, **kwargs):
    # "bind()" the socket object to the server host address and the listening port.
    # IPv4 address and port are required for the "AF_INET" socket family (can be IPv4, hostname, empty). On empty
    # string, the server will accept connections on all available IPv4 interfaces.
    # You need to bind only the main listening socket, no need to throw it to threads
    # Bind will be only set for a server and not for the client. Bind assigns the port to the application that uses
    # it, since it is always needs to be listening for new connections, unlike client that only sends the request
    # and doesn't listen to the specific port.
    try:
        socket_object.bind((ip_address, port))
    # WindowsError is inherited from OSError. It is available when OSError has "WinError" line in it.
    # Off course under linux it will be different.
    except WindowsError as exception_object:
        # Check if the specific "WinError" is "10049"
        # Also, "sys.exc_info()[1].winerror" can be used, but less specific to WindowsError in this case
        # if sys.exc_info()[1].winerror == 10049:
        if exception_object.winerror == 10049:
            message = f"Couldn't bind to interface [{ip_address}] on port [{port}]. Check the address of the interface."
            print_api(message, error_type=True, logger_method="critical", **kwargs)
        # If it's not the specific WinError, then raise the exception regularly anyway.
        else:
            raise


def set_listen_on_socket(socket_object, **kwargs):
    # You need to listen to the main socket once.
    # The number given within 'listen()' is the size of the backlog queue - number of pending requests.
    # Leaving empty will choose default.
    # Specifying number higher than the OS is supporting will truncate to that number. Some linux distributions
    # support maximum of 128 'backlog' sockets. Specifying number higher than 128 will truncate to 128 any way.
    # To determine the maximum listening sockets, you may use the 'socket' library and 'SOMAXCONN' parameter
    # from it.
    socket_object.listen(socket.SOMAXCONN)
    ip_address, port = socket_base.get_destination_address_from_socket(socket_object)

    print_api(f"Listening for new connections on: {ip_address}:{port}", **kwargs)


# ======================================================================================
# Socket Creator Presets

def wrap_socket_with_ssl_context_client___default_certs___ignore_verification(
        socket_object,
        server_hostname: str = None,
        custom_pem_client_certificate_file_path: str = None,
        enable_sslkeylogfile_env_to_client_ssl_context: bool = False,
        sslkeylog_file_path: str = None,
        alpn_protocols: list[str] | None = None
) -> ssl.SSLSocket:
    """
    This function is a preset for wrapping the socket with SSL context for the client.
    It sets the CA default certificates, and ignores the server's certificate verification.

    :param socket_object: socket.socket object
    :param server_hostname: string, hostname of the server. Default is None.
    :param custom_pem_client_certificate_file_path: string, full file path for the client certificate PEM file.
        Default is None.
    :param enable_sslkeylogfile_env_to_client_ssl_context: boolean, enables the SSLKEYLOGFILE environment variable
        to the SSL context. Default is False.
    :param sslkeylog_file_path: string, full file path for the SSL key log file. Default is None.

    :return: ssl.SSLSocket object
    """
    ssl_context: ssl.SSLContext = create_ssl_context_for_client(
        enable_sslkeylogfile_env_to_client_ssl_context=enable_sslkeylogfile_env_to_client_ssl_context,
        sslkeylog_file_path=sslkeylog_file_path,
        alpn_protocols=alpn_protocols)
    set_client_ssl_context_ca_default_certs(ssl_context)
    set_client_ssl_context_certificate_verification_ignore(ssl_context)

    if custom_pem_client_certificate_file_path:
        ssl_context.load_cert_chain(certfile=custom_pem_client_certificate_file_path, keyfile=None)

    ssl_socket: ssl.SSLSocket = wrap_socket_with_ssl_context_client(
        socket_object, ssl_context, server_hostname=server_hostname)

    return ssl_socket

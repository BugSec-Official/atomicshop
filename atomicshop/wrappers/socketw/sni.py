import socket
import ssl
from dataclasses import dataclass, field
from typing import Callable, Any, Optional

from ..loggingw import loggingw
from ...domains import get_domain_without_first_subdomain_if_no_subdomain_return_as_is
from ...print_api import print_api

from . import certificator, creator


@dataclass
class SNIReceivedParameters:
    # Under the sans-io consume+MemoryBIO accept path, ``ssl_socket`` is
    # actually an ``ssl.SSLObject`` (not an ``ssl.SSLSocket``) during the
    # SNI callback — ``SSLContext.wrap_bio`` produces an SSLObject, which
    # has no socket affinity. Properties we read/write on it
    # (``server_hostname``, ``context``) work identically on both types,
    # but addressing calls (``getsockname``, ``getpeername``) do NOT
    # exist on SSLObject, which is why ``raw_socket`` is carried
    # alongside.
    ssl_socket: ssl.SSLObject
    destination_name: str
    ssl_context: ssl.SSLContext
    # The underlying raw TCP socket that the TLS session is riding on.
    # Carried here so ``certificator`` and ``set_socket_server_hostname``
    # can resolve client/server addresses via ``socket_base`` helpers,
    # since ``ssl.SSLObject`` itself has no ``getsockname``/``getpeername``.
    raw_socket: Optional[socket.socket] = field(default=None)


class SNIDefaultCertificateCreationError(Exception):
    pass


class SNISetup:
    """
    Class to handle setting up SNI related features in socket and context.
    """
    def __init__(
            self,
            ca_certificate_name: str | None,
            ca_certificate_filepath: str | None,
            default_server_certificate_usage: bool,
            default_server_certificate_name: str | None,
            default_server_certificate_directory: str | None,
            default_certificate_domain_list: list | None,
            sni_custom_callback_function: Callable[..., Any] | None,
            sni_use_default_callback_function: bool,
            sni_use_default_callback_function_extended: bool,
            sni_add_new_domains_to_default_server_certificate: bool,
            sni_create_server_certificate_for_each_domain: bool,
            sni_server_certificates_cache_directory: str | None,
            sni_get_server_certificate_from_server_socket: bool,
            sni_server_certificate_from_server_socket_download_directory: str | None,
            custom_server_certificate_usage: bool,
            custom_server_certificate_path: str | None,
            custom_private_key_path: str | None,
            forwarding_dns_service_ipv4_list___only_for_localhost: list | None,
            tls: bool,
            domain_from_dns_server: str = None,
            skip_extension_id_list: list = None,
            exceptions_logger: loggingw.ExceptionCsvLogger = None,
            enable_sslkeylogfile_env_to_client_ssl_context: bool = False,
            sslkeylog_file_path: str = None,
            mtls_subdomains: dict | set | None = None,
            client_alpn_offers: list[str] | None = None
    ):
        self.ca_certificate_name = ca_certificate_name
        self.ca_certificate_filepath = ca_certificate_filepath
        self.default_server_certificate_usage = default_server_certificate_usage
        self.default_server_certificate_name = default_server_certificate_name
        self.default_server_certificate_directory = default_server_certificate_directory
        self.default_certificate_domain_list = default_certificate_domain_list
        self.sni_custom_callback_function: Callable[..., Any] | None = sni_custom_callback_function
        self.sni_use_default_callback_function: bool = sni_use_default_callback_function
        self.sni_use_default_callback_function_extended: bool = sni_use_default_callback_function_extended
        self.sni_add_new_domains_to_default_server_certificate = sni_add_new_domains_to_default_server_certificate
        self.sni_create_server_certificate_for_each_domain = sni_create_server_certificate_for_each_domain
        self.sni_server_certificates_cache_directory = sni_server_certificates_cache_directory
        self.sni_get_server_certificate_from_server_socket = sni_get_server_certificate_from_server_socket
        self.sni_server_certificate_from_server_socket_download_directory = (
            sni_server_certificate_from_server_socket_download_directory)
        self.custom_server_certificate_usage = custom_server_certificate_usage
        self.custom_server_certificate_path = custom_server_certificate_path
        self.custom_private_key_path = custom_private_key_path
        self.forwarding_dns_service_ipv4_list___only_for_localhost = (
            forwarding_dns_service_ipv4_list___only_for_localhost)
        self.domain_from_dns_server: str | None = domain_from_dns_server
        self.skip_extension_id_list = skip_extension_id_list
        self.tls = tls
        self.exceptions_logger = exceptions_logger
        self.certificator_instance = None
        self.enable_sslkeylogfile_env_to_client_ssl_context: bool = enable_sslkeylogfile_env_to_client_ssl_context
        self.sslkeylog_file_path: str | None = sslkeylog_file_path
        self.mtls_subdomains = mtls_subdomains
        # Mirror the client's ALPN offers from the inbound ClientHello onto both
        # the initial and SNI-swapped server contexts, so the ALPN negotiation
        # on the inbound leg matches what the client actually asked for.
        self.client_alpn_offers = client_alpn_offers

    def wrap_socket_with_ssl_context_server_sni_extended(
            self,
            socket_object,
            prefetched: bytes = b'',
            print_kwargs: dict = None
    ):
        """
        Build the server SSL context (with SNI callback + certs + ALPN),
        then run the TLS handshake via the sans-io BIO path.

        Why ``prefetched`` is now a parameter
        -------------------------------------
        The caller (``SocketWrapper._connected_socket_thread_worker``) has
        already consumed the first bytes off the socket to parse the
        ClientHello (``ssl_base.consume_client_hello``). OpenSSL would
        deadlock if we let it read from an empty socket buffer while
        waiting for the ClientHello — so the bytes are re-injected into
        the ``MemoryBIO`` by ``creator.wrap_bio_server_with_error_message``.
        Empty bytes are allowed (defensive default) but will result in a
        handshake that has to read the full ClientHello from scratch —
        not an error, just an unnecessary round trip.

        :param socket_object: raw accepted TCP socket. We hand this to
            the BIO pump for ciphertext I/O; we also stash it so the SNI
            callback / certificator can resolve addresses on it (since
            ``SSLObject`` doesn't support ``getsockname``/``getpeername``).
        :param prefetched: bytes already consumed from the socket —
            typically the full ClientHello record parsed by
            ``consume_client_hello``.
        :param print_kwargs: forwarded to ``print_api`` for logging.

        :return: ``(adapter_or_None, error_message_or_None)``. On
            success ``adapter`` is a ``BIOSocketAdapter`` that downstream
            code can use as if it were an ``ssl.SSLSocket``.
        """

        # ---- Stash the raw socket for the SNI callback path ----
        # The SNI callback is invoked mid-handshake with the ``SSLObject``
        # as its first arg, not the adapter (the adapter doesn't exist
        # until handshake completes). Callback code that needs addressing
        # info reads ``self._raw_socket_for_sni`` rather than calling
        # ``getsockname`` on the SSLObject (which would AttributeError).
        self._raw_socket_for_sni: socket.socket = socket_object

        # Create SSL Socket to wrap the raw socket with.
        ssl_context: ssl.SSLContext = creator.create_ssl_context_for_server(
            allow_legacy=True, enable_sslkeylogfile_env_to_client_ssl_context=self.enable_sslkeylogfile_env_to_client_ssl_context,
            sslkeylog_file_path=self.sslkeylog_file_path,
            alpn_protocols=self.client_alpn_offers)

        self.certificator_instance = certificator.Certificator(
            ca_certificate_name=self.ca_certificate_name,
            ca_certificate_filepath=self.ca_certificate_filepath,
            default_server_certificate_usage=self.default_server_certificate_usage,
            default_server_certificate_name=self.default_server_certificate_name,
            default_server_certificate_directory=self.default_server_certificate_directory,
            default_certificate_domain_list=self.default_certificate_domain_list,
            sni_server_certificates_cache_directory=self.sni_server_certificates_cache_directory,
            sni_get_server_certificate_from_server_socket=self.sni_get_server_certificate_from_server_socket,
            sni_server_certificate_from_server_socket_download_directory=(
                self.sni_server_certificate_from_server_socket_download_directory),
            custom_server_certificate_usage=self.custom_server_certificate_usage,
            custom_server_certificate_path=self.custom_server_certificate_path,
            custom_private_key_path=self.custom_private_key_path,
            forwarding_dns_service_ipv4_list___only_for_localhost=(
                self.forwarding_dns_service_ipv4_list___only_for_localhost),
            skip_extension_id_list=self.skip_extension_id_list,
            tls=self.tls,
            enable_sslkeylogfile_env_to_client_ssl_context=self.enable_sslkeylogfile_env_to_client_ssl_context,
            sslkeylog_file_path=self.sslkeylog_file_path,
            mtls_subdomains=self.mtls_subdomains,
            client_alpn_offers=self.client_alpn_offers
        )

        # Add SNI callback function to the SSL context.
        self.add_sni_callback_function_to_ssl_context(ssl_context=ssl_context, print_kwargs=print_kwargs)

        server_certificate_file_path, server_private_key_file_path = \
            self.certificator_instance.select_server_ssl_context_certificate(print_kwargs=print_kwargs)

        # If the user chose 'sni_create_server_certificate_for_each_domain = 1' in the configuration file,
        # it means that 'self.server_certificate_file_path' will be empty, which is OK, since we'll inject
        # dynamically created certificate from certs folder through SNI.
        if server_certificate_file_path:
            creator.load_certificate_and_key_into_server_ssl_context(
                ssl_context, server_certificate_file_path, server_private_key_file_path,
                print_kwargs=print_kwargs)

        # ---- Hand off to the BIO-pumped handshake ----
        # ``wrap_bio_server_with_error_message`` re-injects ``prefetched``
        # into the MemoryBIO, drives the handshake to completion, and
        # returns a ``BIOSocketAdapter`` that duck-types as SSLSocket.
        ssl_socket, error_message = creator.wrap_bio_server_with_error_message(
            raw_socket=socket_object,
            ssl_context=ssl_context,
            prefetched=prefetched,
            domain_from_dns_server=self.domain_from_dns_server,
            print_kwargs=print_kwargs
        )

        return ssl_socket, error_message

    def add_sni_callback_function_to_ssl_context(
            self,
            ssl_context,
            print_kwargs: dict = None
    ):
        """
        Add SNI callback function reference to SSLContext object. Inplace.

        :param ssl_context: SSLContext object.
        :param print_kwargs: dict, that contains all the arguments for 'print_api' function.
        :return:
        """

        # SNI - Server Name Indication: https://en.wikipedia.org/wiki/Server_Name_Indication
        # SNI is extension to TLS protocol to tell the Server what is destination domain that the client is trying to
        # connect. The server knowing the destination domain then can present to the client the appropriate certificate.
        # "sni_callback" method: https://docs.python.org/3/library/ssl.html#ssl.SSLContext.sni_callback
        # The method calls your custom function. If there is SNI present in the TLS request from the client, then the
        # function will be called. Automatically providing 3 parameters from the system: ssl.SSLSocket, The destination
        # server name, current ssl.SSLContext object.
        # If you check the custom function it has all these variables mandatory, since this is what system provides and
        # handled by the system, if SNI is existent.
        # The function is actually called at "accept()" method of the "ssl.SSLSocket"
        # This needs to be set only once on the listening socket
        if self.sni_custom_callback_function:
            # ssl_context.sni_callback = self.sni_custom_callback_function
            ssl_context.set_servername_callback(self.sni_custom_callback_function)

        if self.sni_use_default_callback_function:
            sni_handler_instance = SNIHandler(
                sni_use_default_callback_function_extended=self.sni_use_default_callback_function_extended,
                sni_add_new_domains_to_default_server_certificate=self.sni_add_new_domains_to_default_server_certificate,
                sni_create_server_certificate_for_each_domain=self.sni_create_server_certificate_for_each_domain,
                certificator_instance=self.certificator_instance,
                domain_from_dns_server=self.domain_from_dns_server,
                default_certificate_domain_list=self.default_certificate_domain_list,
                exceptions_logger=self.exceptions_logger,
                enable_sslkeylogfile_env_to_client_ssl_context=(
                    self.certificator_instance.enable_sslkeylogfile_env_to_client_ssl_context),
                sslkeylog_file_path=self.certificator_instance.sslkeylog_file_path,
                client_alpn_offers=self.client_alpn_offers,
                # Pass the raw TCP socket through so the SNI handler /
                # certificator can resolve peer/local addresses on it.
                # ``getattr`` fallback keeps the legacy ``wrap_socket``-based
                # callers working if they haven't set ``_raw_socket_for_sni``.
                raw_socket=getattr(self, '_raw_socket_for_sni', None))
            ssl_context.set_servername_callback(
                sni_handler_instance.setup_sni_callback(print_kwargs=print_kwargs))


class SNIHandler:
    """
    THe class is responsible for handling SNI callback execution.
    """

    def __init__(
            self,
            sni_use_default_callback_function_extended: bool,
            sni_add_new_domains_to_default_server_certificate: bool,
            sni_create_server_certificate_for_each_domain: bool,
            certificator_instance: certificator.Certificator,
            domain_from_dns_server: str,
            default_certificate_domain_list: list,
            exceptions_logger: loggingw.ExceptionCsvLogger,
            enable_sslkeylogfile_env_to_client_ssl_context: bool,
            sslkeylog_file_path: str,
            client_alpn_offers: list[str] | None = None,
            raw_socket: Optional[socket.socket] = None
    ):
        self.sni_use_default_callback_function_extended = sni_use_default_callback_function_extended
        self.sni_add_new_domains_to_default_server_certificate = sni_add_new_domains_to_default_server_certificate
        self.sni_create_server_certificate_for_each_domain = sni_create_server_certificate_for_each_domain
        self.certificator_instance = certificator_instance
        self.domain_from_dns_server: str = domain_from_dns_server
        self.default_certificate_domain_list = default_certificate_domain_list
        self.exceptions_logger = exceptions_logger
        self.enable_sslkeylogfile_env_to_client_ssl_context: bool = enable_sslkeylogfile_env_to_client_ssl_context
        self.sslkeylog_file_path: str = sslkeylog_file_path
        self.client_alpn_offers = client_alpn_offers
        # Raw TCP socket the handshake is riding on. Needed because the SNI
        # callback receives an ``ssl.SSLObject`` (from ``wrap_bio``) which
        # has no ``getsockname``/``getpeername`` — address lookups go
        # through this raw socket instead.
        self.raw_socket: Optional[socket.socket] = raw_socket

        # noinspection PyTypeChecker
        self.sni_received_parameters: SNIReceivedParameters = None

    # Server Name Indication (SNI) is an extension to the Transport Layer Security (TLS) computer networking protocol.
    # Function to handle server's SSLContext's SNI callback function.
    # This is actually called first during "accept()" method of the "ssl.SSLSocket" then comes accept itself.
    # This happens in 'ssl.py' module in 'self._sslobj.do_handshake()' function.
    def setup_sni_callback(
            self,
            print_kwargs: dict = None
    ):
        """
        Setup SNI callback function.
        :param print_kwargs: dict, that contains all the arguments for 'print_api' function.
        :return:
        """

        def sni_handle(
                sni_ssl_socket,
                sni_destination_name: str,
                sni_ssl_context: ssl.SSLContext):
            # Note: ``sni_ssl_socket`` is typed as ``ssl.SSLObject`` here
            # (not ``ssl.SSLSocket``) — ``ssl.SSLContext.wrap_bio`` yields
            # an SSLObject, which is what the BIO-pumped accept path now
            # uses. ``server_hostname`` is read-only on SSLObject (Python
            # populates it from the ClientHello SNI extension before
            # invoking this callback); ``context`` is read/write on both.

            try:
                # If 'sni_execute_extended' was set to True.
                if self.sni_use_default_callback_function_extended:
                    self.sni_received_parameters = SNIReceivedParameters(
                        ssl_socket=sni_ssl_socket,
                        destination_name=sni_destination_name,
                        ssl_context=sni_ssl_context,
                        # Propagate the raw TCP socket through to
                        # ``certificator`` etc. so they can resolve local
                        # and peer addresses without going through the
                        # SSLObject (which doesn't support those calls).
                        raw_socket=self.raw_socket,
                    )

                    self.sni_handle_extended(print_kwargs=print_kwargs)
            except Exception as e:
                self.exceptions_logger.write(e)

        return sni_handle

    def sni_handle_extended(
            self,
            print_kwargs: dict = None
    ):
        # Set 'server_hostname' for the socket.
        self.set_socket_server_hostname(print_kwargs=print_kwargs)

        # If 'sni_default_server_certificates_addons' was set to 'True' in the 'config.ini'.
        # This section will add all the new domains that hit the server to default certificate SAN with wildcard.
        if self.sni_add_new_domains_to_default_server_certificate:
            self.sni_add_domain_to_default_server_certificate(print_kwargs=print_kwargs)

        # If SNI server certificate creation was set to 'True', we'll create certificate for each incoming domain if
        # non-existent in certificates cache folder.
        if self.sni_create_server_certificate_for_each_domain:
            self.certificator_instance.create_use_sni_server_certificate_ca_signed(
                sni_received_parameters=self.sni_received_parameters, print_kwargs=print_kwargs)

    def set_socket_server_hostname(
            self,
            print_kwargs: dict = None
    ):
        service_name_from_sni = None

        # Try on general settings in the SNI function.
        try:
            # Check if SNI was passed. If no SNI was passed.
            if not self.sni_received_parameters.destination_name:
                # If DNS server is enabled we'll get the domain from dns server.
                if self.domain_from_dns_server:
                    self.sni_received_parameters.destination_name = self.domain_from_dns_server
                    print_api("SNI Passed: False", color="yellow", **(print_kwargs or {}))

                    message = f"SNI Handler: No SNI was passed, using domain from DNS Server: {self.domain_from_dns_server}"
                    print_api(message, color="yellow", **(print_kwargs or {}))
                # If DNS server is disabled, the domain from dns server will be empty.
                else:
                    print_api("SNI Passed: False", color="yellow", **(print_kwargs or {}))

                    message = (
                        f"SNI Handler: No SNI was passed, No domain passed from DNS Server. Service name will be 'None'.")
                    print_api(message, color="yellow", **(print_kwargs or {}))

            print_api("SNI Passed: True", **(print_kwargs or {}))
            # Resolve the local port via the raw socket. The ``ssl_socket``
            # field is an ``SSLObject`` under the BIO accept path and does
            # not expose ``getsockname``. The raw socket is always carried
            # on ``sni_received_parameters.raw_socket`` for this purpose.
            local_port_str = "?"
            if self.sni_received_parameters.raw_socket is not None:
                try:
                    local_port_str = str(
                        self.sni_received_parameters.raw_socket.getsockname()[1])
                except OSError:
                    pass
            message = (
                f"SNI Handler: port {local_port_str}: "
                f"Incoming connection for [{self.sni_received_parameters.destination_name}]")
            print_api(message, **(print_kwargs or {}))
        except Exception as exception_object:
            message = f"SNI Handler: Undocumented exception general settings section: {exception_object}"
            print_api(message, error_type=True, logger_method="error", traceback_string=True,
                      **(print_kwargs or {}))
            pass

    def sni_add_domain_to_default_server_certificate(
            self,
            print_kwargs: dict = None
    ):
        # Check if incoming domain is already in the parent domains of 'domains_all_times' list.
        if not any(x in self.sni_received_parameters.destination_name for x in
                   self.default_certificate_domain_list):
            message = f"SNI Handler: Current domain is not in known domains list. Adding."
            print_api(message, **(print_kwargs or {}))
            # In the past was using 'certauth' to extract tlds, but it works only in online mode, so rewrote
            # the function to disable online fetching of TLD snapshot.
            # Initialize 'certauth' object.
            # certificate_object = CertificateAuthority(certificate_ca_name, certificate_ca_filepath)
            # Extract parent domain from the current SNI domain.
            # parent_domain = certificate_object.get_wildcard_domain(service_name_from_sni)

            # Extract parent domain from the current SNI domain.
            parent_domain = get_domain_without_first_subdomain_if_no_subdomain_return_as_is(
                self.sni_received_parameters.destination_name)
            # Add the parent domain to the known domains list.
            self.default_certificate_domain_list.append(parent_domain)

            default_server_certificate_path, subject_alternate_names = \
                self.certificator_instance.create_overwrite_default_server_certificate_ca_signed()

            if default_server_certificate_path:
                message = f"SNI Handler: Default Server Certificate was created / overwritten: " \
                            f"{default_server_certificate_path}"
                print_api(message, **(print_kwargs or {}))

                message = f"SNI Handler: Server Certificate current 'Subject Alternative Names': " \
                          f"{subject_alternate_names}"
                print_api(message, **(print_kwargs or {}))

                # Since new default certificate was created we need to create new SSLContext and add the certificate.
                # You need to build new context and exchange the context that being inherited from the main socket,
                # or else the context will receive previous certificate each time.
                self.sni_received_parameters.ssl_socket.context = (
                    creator.create_server_ssl_context___load_certificate_and_key(
                        default_server_certificate_path,
                        None,
                        inherit_from=self.sni_received_parameters.ssl_socket.context,
                        enable_sslkeylogfile_env_to_client_ssl_context=self.enable_sslkeylogfile_env_to_client_ssl_context,
                        sslkeylog_file_path=self.sslkeylog_file_path,
                        alpn_protocols=self.client_alpn_offers
                    )
                )
            else:
                message = f"Couldn't create / overwrite Default Server Certificate: {default_server_certificate_path}"
                raise SNIDefaultCertificateCreationError(message)

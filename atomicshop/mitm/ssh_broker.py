"""Central SSH broker: persistent SSH connections per target computer, shared by every
TCP server process for port->command-line (process-name) lookups over queues.

paramiko transports are not safe to share across threads, so every connection is used by one query at
a time. Each host has its own request queue served by its own worker threads (each owning its own
connection), so a slow or unreachable host only backs up its own queue and never delays other hosts."""
import itertools
import logging
import queue
import threading
import time

from . import config_static
from .. import ssh_remote, package_mains_processor
from ..print_api import print_api
from ..ssh_remote import SSHRemote
from ..wrappers.loggingw import loggingw
from ..wrappers.socketw.process_getter import GetCommandLine


# Worker-side wait ceiling. Must exceed ssh_remote.SSH_READ_TIMEOUT (30) so the broker's own
# read timeout fires first and the caller gets its error string, not a bare timeout here.
SSH_LOOKUP_TIMEOUT: float = 45.0

# Worker threads per host. Each thread owns its own SSH connection to the host, so a burst of
# connections from one host resolves in parallel while no connection is shared between threads.
_THREADS_PER_HOST: int = 3

# Fail fast: after this many failed lookups in a row (couldn't connect / log in / find Python, or the
# SSH read timed out), the host is treated as down and its requests are answered at once without SSH
# for _HOST_DOWN_SECONDS. After that a single request probes the host again.
_HOST_FAIL_LIMIT: int = 3
_HOST_DOWN_SECONDS: float = 30.0

# Start of the error text ssh_remote.SSHRemote.remote_execution returns when reading the output hung.
_READ_TIMEOUT_PREFIX: str = "SSH read timed out"


class SSHLookupClient:
    """Worker-side handle, lives in each TCP server process. Thread-safe. Never raises from lookup()."""

    def __init__(self, request_queue, response_queue, worker_id: int):
        self._request_queue = request_queue
        self._response_queue = response_queue
        self._worker_id: int = worker_id
        self._ids = itertools.count(1)                  # monotonic request ids
        self._pending: dict[int, queue.Queue] = {}      # request_id -> single-slot result
        self._lock = threading.Lock()                   # guards _pending
        # One daemon reader drains response_queue and routes each result to its waiting caller.
        self._reader = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader.start()

    def _reader_loop(self) -> None:
        while True:
            item = self._response_queue.get()
            if item is None:                            # close() sentinel
                break
            request_id, result = item
            with self._lock:
                slot = self._pending.pop(request_id, None)
            # Unknown id => the caller already timed out and left; discard.
            if slot is not None:
                slot.put(result)

    def lookup(
            self,
            source_ip: str,
            source_port: int,
            ssh_user: str,
            ssh_pass: str,
            timeout: float = SSH_LOOKUP_TIMEOUT
    ) -> str:
        request_id: int = next(self._ids)
        slot: queue.Queue = queue.Queue(maxsize=1)
        with self._lock:
            self._pending[request_id] = slot
        try:
            # The timeout travels with the request, so the broker can skip it once nobody waits for it.
            self._request_queue.put(
                (self._worker_id, request_id, source_ip, source_port, ssh_user, ssh_pass, timeout))
            return slot.get(timeout=timeout)
        except queue.Empty:
            with self._lock:
                self._pending.pop(request_id, None)
            return f"SSH lookup timed out after {timeout}s"
        except Exception as e:
            with self._lock:
                self._pending.pop(request_id, None)
            return f"SSH lookup client error: {e}"

    def close(self) -> None:
        """Stop the reader thread."""
        try:
            self._response_queue.put(None)
        except Exception:
            pass


class _HostState:
    """Fail-fast bookkeeping for one host, shared by that host's worker threads."""

    def __init__(self):
        self.cond = threading.Condition()   # guards the fields below; notified when a lookup finishes
        self.failures: int = 0              # failed lookups in a row
        self.in_flight: int = 0             # lookups running right now
        self.down_until: float = 0.0        # time.monotonic() until which the host is not tried
        self.probing: bool = False          # one lookup is re-testing the host after the down window
        self.last_error: str = ''


class SSHBroker:
    """Owns persistent SSHRemote connections per target host and answers port->command-line queries.
    Every host has its own request queue served by its own worker threads (started on the host's
    first request); each thread uses only its own connection, and different hosts resolve
    independently: a host that is down backs up only its own queue.
    Requests whose caller already gave up are skipped, and a host that keeps failing is answered
    without SSH for a while (fail fast) instead of making each of its connections wait on it."""

    def __init__(
            self,
            response_queues: list,
            ssh_script_to_execute: str,
            logger: logging.Logger = None,
            threads_per_host: int = _THREADS_PER_HOST
    ):
        self._response_queues: list = response_queues
        self._logger: logging.Logger = logger
        self._threads_per_host: int = threads_per_host
        # Built once; reads the SSH script bundled in the package resources.
        self._package_processor = package_mains_processor.PackageMainsProcessor(
            script_file_stem=ssh_script_to_execute)
        self._clients: dict[tuple[str, int], SSHRemote] = {}    # (host ip, worker slot) -> connection
        self._host_queues: dict[str, queue.Queue] = {}          # host ip -> that host's pending requests
        self._dict_lock = threading.Lock()                      # guards _clients and _host_queues

    def _host_queue(self, ip: str) -> queue.Queue:
        """Get the host's request queue, starting the host's worker threads on first use."""
        with self._dict_lock:
            host_queue = self._host_queues.get(ip)
            if host_queue is None:
                host_queue = queue.Queue()
                self._host_queues[ip] = host_queue
                host_state = _HostState()
                for slot in range(self._threads_per_host):
                    threading.Thread(
                        target=self._host_worker_loop, args=(slot, host_queue, host_state),
                        name=f'ssh_broker_{ip}_{slot}', daemon=True).start()
            return host_queue

    def _host_worker_loop(self, slot: int, host_queue: queue.Queue, host_state: _HostState) -> None:
        """One of a host's workers: resolve the host's requests on this slot's own connection;
        stop on the None sentinel."""
        while True:
            msg = host_queue.get()
            if msg is None:
                break
            self._handle(slot, host_state, *msg)

    def _get_or_create_client(self, ip: str, slot: int, ssh_user: str, ssh_pass: str) -> SSHRemote:
        with self._dict_lock:
            client = self._clients.get((ip, slot))
            if client is None:
                client = SSHRemote(ip, ssh_user, ssh_pass, logger=self._logger)
                self._clients[(ip, slot)] = client
            return client

    def _forget_client(self, ip: str, slot: int) -> None:
        """Drop one worker's connection so that worker's next request reconnects fresh."""
        with self._dict_lock:
            client = self._clients.pop((ip, slot), None)
        if client is not None:
            try:
                client.close()
            except Exception:
                pass

    def _run_lookup(self, client: SSHRemote, ip: str, port: int) -> str:
        """Seam: the actual command-line lookup (real SSH / localhost). Stubbed in tests."""
        return GetCommandLine(
            client_ip=ip,
            client_port=port,
            package_processor=self._package_processor,
            ssh_client=client,
            logger=self._logger,
        ).get_process_name(print_kwargs={'logger': self._logger})

    def _admit(self, host_state: _HostState, deadline: float) -> str | None:
        """Decide whether this request may run an SSH lookup now. None means go ahead (the lookup's
        outcome must then be reported through _record_result); otherwise returns the answer to send
        without SSH:
        - The caller already stopped waiting: skip; a lookup now would only delay the requests behind it.
        - Host down: answer at once. After the down window exactly one request (the probe) goes through,
          the rest keep failing fast until the probe's result is known.
        - Host with recent failures: never run more lookups than could still be needed to reach the
          fail limit; wait for a running one to finish instead (usually moments), then decide again."""
        with host_state.cond:
            while True:
                if time.monotonic() > deadline:
                    return "SSH lookup skipped: the request expired while queued"
                if host_state.failures >= _HOST_FAIL_LIMIT:
                    retry_in: float = host_state.down_until - time.monotonic()
                    if retry_in <= 0 and not host_state.probing:
                        host_state.probing = True
                        host_state.in_flight += 1
                        return None
                    retry: str = f"next retry in {retry_in:.0f}s" if retry_in > 0 else "retry in progress"
                    return (f"SSH lookup skipped: host down after {host_state.failures} failed lookups, "
                            f"{retry}. Last error: {host_state.last_error}")
                if host_state.failures == 0 or host_state.failures + host_state.in_flight < _HOST_FAIL_LIMIT:
                    host_state.in_flight += 1
                    return None
                host_state.cond.wait(timeout=deadline - time.monotonic())

    def _record_result(self, ip: str, host_state: _HostState, error: str | None) -> None:
        """Feed one lookup's outcome into the host's fail-fast state; log when the host goes down or recovers."""
        with host_state.cond:
            was_down: bool = host_state.failures >= _HOST_FAIL_LIMIT
            host_state.in_flight -= 1
            host_state.probing = False
            if error is None:
                host_state.failures = 0
            else:
                host_state.failures += 1
                host_state.last_error = error
                if host_state.failures >= _HOST_FAIL_LIMIT:
                    host_state.down_until = time.monotonic() + _HOST_DOWN_SECONDS
            failures: int = host_state.failures
            host_state.cond.notify_all()

        if error is None and was_down:
            print_api(f"SSH host [{ip}] is reachable again, lookups resumed.",
                      logger=self._logger, logger_method='info')
        elif error is not None and failures == _HOST_FAIL_LIMIT:
            print_api(
                f"SSH host [{ip}] marked down after {failures} failed lookups in a row; its requests are "
                f"answered without SSH, retrying every {_HOST_DOWN_SECONDS:.0f}s. Last error: {error}",
                logger=self._logger, logger_method='warning')

    def _lookup_and_record(self, slot, host_state, source_ip, source_port, ssh_user, ssh_pass) -> str:
        """Run the lookup on this worker's own connection; its outcome is always recorded for fail fast."""
        error: str | None = None
        try:
            client = self._get_or_create_client(source_ip, slot, ssh_user, ssh_pass)
            result = self._run_lookup(client, source_ip, source_port)
            if isinstance(result, str) and result.startswith(_READ_TIMEOUT_PREFIX):
                # The connection hung: reconnect on the next request, and count it as a failed lookup.
                error = result
                self._forget_client(source_ip, slot)
        except Exception as e:
            result = error = f"SSH lookup error: {e}"
            self._forget_client(source_ip, slot)
        finally:
            self._record_result(source_ip, host_state, error)
        return result

    def _handle(self, slot, host_state, deadline, worker_id, request_id, source_ip, source_port,
                ssh_user, ssh_pass) -> None:
        """Resolve one request and ALWAYS send exactly one response back.
        Runs on one of source_ip's workers; 'slot' selects that worker's own connection."""
        try:
            result = self._admit(host_state, deadline)
            if result is None:
                result = self._lookup_and_record(
                    slot, host_state, source_ip, source_port, ssh_user, ssh_pass)
        except Exception as e:
            # Any unexpected failure still owes the caller a response.
            result = f"SSH broker error: {e}"
        finally:
            try:
                self._response_queues[worker_id].put((request_id, result))
            except Exception:
                pass                                    # response queue gone; nothing more to do

    def serve_forever(self, request_queue) -> None:
        """Dispatch loop: route each request to its host's queue; stop on the None sentinel."""
        try:
            while True:
                msg = request_queue.get()
                if msg is None:
                    break
                worker_id, request_id, source_ip, source_port, ssh_user, ssh_pass, timeout = msg
                # The caller gives up 'timeout' seconds after sending; once past this deadline (on this
                # process's clock) the request is skipped instead of looked up.
                deadline: float = time.monotonic() + timeout
                self._host_queue(source_ip).put(
                    (deadline, worker_id, request_id, source_ip, source_port, ssh_user, ssh_pass))
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """Stop every host worker and close every cached connection (best-effort)."""
        with self._dict_lock:
            host_queues = list(self._host_queues.values())
            connections = list(self._clients.keys())
        for host_queue in host_queues:
            for _ in range(self._threads_per_host):
                host_queue.put(None)
        for ip, slot in connections:
            self._forget_client(ip, slot)


def ssh_broker_worker(
        request_queue,
        response_queues: list,
        config_file_path: str,
        ssh_script_to_execute: str,
        is_ready_event,
        network_logger_name: str,
        network_logger_queue
) -> None:
    """Process entrypoint (spawn-safe): set up logging, build the broker, run the dispatch loop."""
    # Load config_static per process, since it is not shared between processes.
    config_static.load_config(config_file_path, print_kwargs=dict(stdout=False))

    # Network logger with a queue handler -> the parent's log-queue listener.
    _ = loggingw.create_logger(
        logger_name=network_logger_name,
        add_queue_handler=True,
        log_queue=network_logger_queue,
    )
    # Route paramiko's transport warnings through the same queue (formatted), not bare to stderr.
    _ = loggingw.create_logger(
        logger_name="paramiko",
        add_queue_handler=True,
        log_queue=network_logger_queue,
        logging_level="WARNING",
    )
    logger: logging.Logger = loggingw.get_logger_with_level(f'{network_logger_name}.system')

    broker = SSHBroker(
        response_queues=response_queues,
        ssh_script_to_execute=ssh_script_to_execute,
        logger=logger,
    )
    is_ready_event.set()
    broker.serve_forever(request_queue)

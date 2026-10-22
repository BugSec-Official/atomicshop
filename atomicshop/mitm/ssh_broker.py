"""Central SSH broker: persistent SSH connections per target computer, shared by every
TCP server process for port->command-line (process-name) lookups over queues.

paramiko transports are not safe to share across threads, so every connection is used by one lookup at
a time. Healthy hosts share one fixed pool of threads; a host whose lookup fails gets its own thread
until a lookup there succeeds, so a slow or unreachable host never holds pool threads.
Tuning values: config_static.ProcessName.ssh_*."""
import collections
import dataclasses
import itertools
import logging
import queue
import threading
import time

from . import config_static
from .. import package_mains_processor
from ..print_api import print_api
from ..ssh_remote import SSHRemote
from ..wrappers.loggingw import loggingw
from ..wrappers.socketw.process_getter import GetCommandLine


# Worker-side wait ceiling. Must exceed ssh_remote.SSH_READ_TIMEOUT (30) so the broker's own
# read timeout fires first and the caller gets its error string, not a bare timeout here.
SSH_LOOKUP_TIMEOUT: float = 45.0

# Start of the error text ssh_remote.SSHRemote.remote_execution returns when reading the output hung.
_READ_TIMEOUT_PREFIX: str = "SSH read timed out"

_EXPIRED_RESULT: str = "SSH lookup skipped: the request expired while queued"


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


@dataclasses.dataclass
class _Request:
    deadline: float                 # time.monotonic() after which the caller no longer waits
    worker_id: int
    request_id: int
    ip: str
    port: int
    ssh_user: str
    ssh_pass: str


class _HealthyHost:
    """Pool side of one host: its free connections and the requests waiting for one."""

    def __init__(self):
        self.idle: list[tuple[SSHRemote, float]] = []           # (connection, last used) not in use
        self.busy: int = 0                                      # requests holding a connection slot
        self.line: collections.deque = collections.deque()     # requests waiting for a free slot


class _ProblemHost:
    """Row of a problematic host: fail-fast state and the line of its dedicated thread."""

    def __init__(self, lock: threading.Lock):
        self.failures: int = 0                                  # failed lookups in a row
        self.last_error: str = ''
        self.down_until: float = 0.0                            # answer "host down" without SSH until then
        self.last_request: float = time.monotonic()
        self.line: collections.deque = collections.deque()
        self.thread: threading.Thread | None = None             # None: not started yet, or closed when idle
        self.wake = threading.Condition(lock)                   # new request / closed
        self.closed: bool = False                               # recovered or shutting down


class SSHBroker:
    """Owns persistent SSHRemote connections per target host and answers port->command-line queries.
    Healthy hosts run on a fixed pool of threads, each host on up to ssh_connections_per_host
    connections; its extra requests wait in the host's own line, never inside a pool thread.
    The first failed lookup gives the host its own thread (one connection, one request at a time, fail
    fast after repeated failures) until a lookup succeeds; then the host returns to the pool.
    Unused connections, idle dedicated threads and old problem rows are closed/forgotten over time."""

    def __init__(
            self,
            response_queues: list,
            ssh_script_to_execute: str,
            logger: logging.Logger = None
    ):
        self._response_queues: list = response_queues
        self._logger: logging.Logger = logger
        # Built once; reads the SSH script bundled in the package resources.
        self._package_processor = package_mains_processor.PackageMainsProcessor(
            script_file_stem=ssh_script_to_execute)

        settings = config_static.ProcessName
        self._pool_size: int = settings.ssh_pool_threads
        self._connections_per_host: int = settings.ssh_connections_per_host
        self._fail_limit: int = settings.ssh_host_fail_limit
        self._down_seconds: float = settings.ssh_host_down_seconds
        self._problem_thread_idle: float = settings.ssh_problem_thread_idle_seconds
        self._connection_idle: float = settings.ssh_connection_idle_seconds
        self._forget_after: float = settings.ssh_problem_host_forget_seconds
        # How often the dispatch loop closes idle connections and drops old rows.
        self._sweep_interval: float = max(0.05, min(self._connection_idle, self._forget_after) / 5)

        self._lock = threading.Lock()                           # guards everything below
        self._healthy: dict[str, _HealthyHost] = {}
        self._problems: dict[str, _ProblemHost] = {}
        self._pool_queue: queue.Queue = queue.Queue()           # requests holding a slot, for the pool
        self._pool_threads: list[threading.Thread] = []
        self._stopped: bool = False

    # --- lookup and response ---

    def _run_lookup(self, client: SSHRemote, ip: str, port: int) -> str:
        """Seam: the actual command-line lookup (real SSH / localhost). Stubbed in tests."""
        return GetCommandLine(
            client_ip=ip,
            client_port=port,
            package_processor=self._package_processor,
            ssh_client=client,
            logger=self._logger,
        ).get_process_name(print_kwargs={'logger': self._logger})

    def _lookup(self, request: _Request, connection: SSHRemote | None) -> tuple[str, str | None, SSHRemote | None]:
        """Run one lookup on 'connection' (a new one when None).
        Returns (result, error or None, the connection to keep; None when it failed and was closed).
        Failed = couldn't connect / log in / find Python (exception) or the SSH read hung."""
        error: str | None = None
        try:
            if connection is None:
                connection = SSHRemote(request.ip, request.ssh_user, request.ssh_pass, logger=self._logger)
            result = self._run_lookup(connection, request.ip, request.port)
            if isinstance(result, str) and result.startswith(_READ_TIMEOUT_PREFIX):
                error = result
        except Exception as e:
            result = error = f"SSH lookup error: {e}"
        if error is not None and connection is not None:
            self._close(connection)
            connection = None
        return result, error, connection

    def _respond(self, request: _Request, result: str) -> None:
        try:
            self._response_queues[request.worker_id].put((request.request_id, result))
        except Exception:
            pass                                    # response queue gone; nothing more to do

    @staticmethod
    def _close(connection: SSHRemote) -> None:
        try:
            connection.close()
        except Exception:
            pass

    # --- routing (all *_locked methods run under self._lock) ---

    def _route_locked(self, request: _Request) -> None:
        """Send a request to its host's dedicated thread if the host is problematic, else to the pool:
        straight away while the host has a free connection slot, otherwise into the host's line."""
        row = self._problems.get(request.ip)
        if (row is not None and row.thread is None
                and time.monotonic() - row.last_request > self._forget_after):
            del self._problems[request.ip]
            row = None
        if row is not None:
            self._queue_for_problem_thread_locked(request.ip, row, request)
            return

        host = self._healthy.setdefault(request.ip, _HealthyHost())
        if host.busy < self._connections_per_host:
            host.busy += 1
            self._pool_queue.put(request)
        else:
            host.line.append(request)

    def _dispatch_waiting_locked(self, host: _HealthyHost) -> None:
        while host.line and host.busy < self._connections_per_host:
            host.busy += 1
            self._pool_queue.put(host.line.popleft())

    def _queue_for_problem_thread_locked(self, ip: str, row: _ProblemHost, request: _Request) -> None:
        """Add to the host's dedicated line, starting the thread if it isn't running."""
        row.last_request = time.monotonic()
        row.line.append(request)
        if row.thread is None:
            row.thread = threading.Thread(
                target=self._problem_thread_loop, args=(ip, row), name=f'ssh_broker_host_{ip}', daemon=True)
            row.thread.start()
        else:
            row.wake.notify()

    def _record_failure_locked(self, ip: str, error: str) -> None:
        """Count a failed lookup. The first one makes the host problematic: requests waiting in its pool
        line follow it to its own thread."""
        row = self._problems.get(ip)
        if row is None:
            row = _ProblemHost(self._lock)
            self._problems[ip] = row
            print_api(f"SSH host [{ip}] lookup failed; its lookups now run on a dedicated thread until one "
                      f"succeeds. Error: {error}", logger=self._logger, logger_method='info')
            host = self._healthy.get(ip)
            if host is not None:
                while host.line:
                    self._queue_for_problem_thread_locked(ip, row, host.line.popleft())

        row.failures += 1
        row.last_error = error
        if row.failures >= self._fail_limit:
            row.down_until = time.monotonic() + self._down_seconds
            if row.failures == self._fail_limit:
                print_api(
                    f"SSH host [{ip}] marked down after {row.failures} failed lookups in a row; its requests are "
                    f"answered without SSH, retrying every {self._down_seconds:.0f}s. Last error: {error}",
                    logger=self._logger, logger_method='warning')

    def _recover_locked(self, ip: str) -> None:
        """A lookup succeeded: delete the host's row, close its dedicated thread, its waiting requests go to the pool."""
        row = self._problems.pop(ip, None)
        if row is None:
            return
        row.closed = True
        row.wake.notify_all()
        print_api(f"SSH host [{ip}] lookups succeed again; back on the shared pool.",
                  logger=self._logger, logger_method='info')
        while row.line:
            self._route_locked(row.line.popleft())

    def _keep_connection_locked(self, ip: str, connection: SSHRemote | None) -> SSHRemote | None:
        """Put a working connection on the host's idle list; returns it back if it is not needed (to close)."""
        if connection is None or self._stopped:
            return connection
        host = self._healthy.setdefault(ip, _HealthyHost())
        if len(host.idle) + host.busy >= self._connections_per_host:
            return connection
        host.idle.append((connection, time.monotonic()))
        return None

    # --- shared pool ---

    def _pool_thread_loop(self) -> None:
        while True:
            request = self._pool_queue.get()
            if request is None:
                break
            try:
                self._run_pool_request(request)
            except Exception as e:
                # Any unexpected failure still owes the caller a response; the pool thread keeps serving.
                self._respond(request, f"SSH broker error: {e}")

    def _run_pool_request(self, request: _Request) -> None:
        """Run one request that holds a connection slot of its healthy host, then pass the slot on."""
        connection: SSHRemote | None = None
        with self._lock:
            host = self._healthy[request.ip]
            row = self._problems.get(request.ip)
            if row is not None:
                # The host turned problematic while this request waited for a pool thread: it follows the host.
                host.busy -= 1
                self._queue_for_problem_thread_locked(request.ip, row, request)
                return
            expired: bool = time.monotonic() > request.deadline
            if not expired and host.idle:
                connection, _ = host.idle.pop()

        result, error = _EXPIRED_RESULT, None
        try:
            if not expired:
                result, error, connection = self._lookup(request, connection)
            self._respond(request, result)
        finally:
            with self._lock:
                host.busy -= 1
                connection = self._keep_connection_locked(request.ip, connection)
                if error is not None:
                    self._record_failure_locked(request.ip, error)
                elif not expired and request.ip in self._problems:
                    # Was already running when the host turned problematic, and it worked: the host is fine.
                    self._recover_locked(request.ip)
                self._dispatch_waiting_locked(host)
            if connection is not None:
                self._close(connection)

    # --- dedicated thread of a problematic host ---

    def _problem_thread_loop(self, ip: str, row: _ProblemHost) -> None:
        """One request at a time on one connection, with fail fast. Ends when a lookup succeeds, on shutdown,
        or after ssh_problem_thread_idle_seconds without requests (the row stays; the next request starts
        a new thread)."""
        connection: SSHRemote | None = None
        try:
            while True:
                with self._lock:
                    while not row.line and not row.closed:
                        if not row.wake.wait(timeout=self._problem_thread_idle) and not row.line:
                            row.thread = None               # idle: close; set under the lock so no request is missed
                            return
                    if row.closed:
                        return
                    request: _Request = row.line.popleft()
                    answer: str | None = self._answer_without_ssh_locked(row, request)
                if answer is not None:
                    self._respond(request, answer)
                    continue
                try:
                    result, error, connection = self._lookup(request, connection)
                    self._respond(request, result)
                except Exception as e:
                    self._respond(request, f"SSH broker error: {e}")
                    continue
                with self._lock:
                    if error is not None:
                        self._record_failure_locked(ip, error)
                        continue
                    connection = self._keep_connection_locked(ip, connection)
                    self._recover_locked(ip)
                return
        finally:
            if connection is not None:
                self._close(connection)

    def _answer_without_ssh_locked(self, row: _ProblemHost, request: _Request) -> str | None:
        """The answer for a request that must not run a lookup (caller gave up / host down), else None.
        After the down window the next request is the retry; requests behind it wait for its result."""
        now: float = time.monotonic()
        if now > request.deadline:
            return _EXPIRED_RESULT
        if row.failures >= self._fail_limit and now < row.down_until:
            return (f"SSH lookup skipped: host down after {row.failures} failed lookups, "
                    f"next retry in {row.down_until - now:.0f}s. Last error: {row.last_error}")
        return None

    # --- dispatch loop ---

    def _sweep(self) -> None:
        """Close connections unused for ssh_connection_idle_seconds; forget hosts with nothing left, and
        problem rows without requests for ssh_problem_host_forget_seconds."""
        now: float = time.monotonic()
        to_close: list[SSHRemote] = []
        with self._lock:
            for ip, host in list(self._healthy.items()):
                to_close += [connection for connection, used in host.idle if now - used >= self._connection_idle]
                host.idle = [(connection, used) for connection, used in host.idle if now - used < self._connection_idle]
                if not host.idle and not host.busy and not host.line:
                    del self._healthy[ip]
            for ip, row in list(self._problems.items()):
                if row.thread is None and now - row.last_request > self._forget_after:
                    del self._problems[ip]
        for connection in to_close:
            self._close(connection)

    def serve_forever(self, request_queue) -> None:
        """Dispatch loop: route each request to the pool or its host's dedicated thread, sweep idle
        resources between requests; stop on the None sentinel."""
        for index in range(self._pool_size):
            thread = threading.Thread(target=self._pool_thread_loop, name=f'ssh_broker_pool_{index}', daemon=True)
            thread.start()
            self._pool_threads.append(thread)
        try:
            next_sweep: float = time.monotonic() + self._sweep_interval
            while True:
                try:
                    msg = request_queue.get(timeout=self._sweep_interval)
                except queue.Empty:
                    msg = ()
                if msg is None:
                    break
                if msg:
                    worker_id, request_id, source_ip, source_port, ssh_user, ssh_pass, timeout = msg
                    # The caller gives up 'timeout' seconds after sending; once past this deadline (on this
                    # process's clock) the request is skipped instead of looked up.
                    request = _Request(time.monotonic() + timeout, worker_id, request_id, source_ip,
                                       source_port, ssh_user, ssh_pass)
                    with self._lock:
                        self._route_locked(request)
                if time.monotonic() >= next_sweep:
                    self._sweep()
                    next_sweep = time.monotonic() + self._sweep_interval
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """Stop the pool and every dedicated thread, close every idle connection (best-effort)."""
        with self._lock:
            self._stopped = True
            for row in self._problems.values():
                row.closed = True
                row.wake.notify_all()
            connections = [connection for host in self._healthy.values() for connection, _ in host.idle]
            for host in self._healthy.values():
                host.idle = []
        for _ in self._pool_threads:
            self._pool_queue.put(None)
        for connection in connections:
            self._close(connection)


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

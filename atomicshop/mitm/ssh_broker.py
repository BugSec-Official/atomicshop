"""Central SSH broker: one persistent SSH connection per target computer, shared by every
TCP server process for port->command-line (process-name) lookups over queues.

paramiko transports are not safe to share across threads, so each host is served by a single
connection used by one query at a time (per-host lock); different hosts resolve in parallel."""
import concurrent.futures
import itertools
import logging
import queue
import threading

from . import config_static
from .. import ssh_remote, package_mains_processor
from ..ssh_remote import SSHRemote
from ..wrappers.loggingw import loggingw
from ..wrappers.socketw.process_getter import GetCommandLine


# Worker-side wait ceiling. Must exceed ssh_remote.SSH_READ_TIMEOUT (30) so the broker's own
# read timeout fires first and the caller gets its error string, not a bare timeout here.
SSH_LOOKUP_TIMEOUT: float = 45.0

# Pool size for parallel per-host resolves; same host is still serialized by its host lock.
_MAX_RESOLVE_WORKERS: int = 16


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
            self._request_queue.put(
                (self._worker_id, request_id, source_ip, source_port, ssh_user, ssh_pass))
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


class SSHBroker:
    """Owns one persistent SSHRemote per target host and answers port->command-line queries.
    Different hosts resolve in parallel on a thread pool; the same host is serialized by its
    per-host lock, so that host's single connection is used by one query at a time."""

    def __init__(
            self,
            response_queues: list,
            ssh_script_to_execute: str,
            logger: logging.Logger = None,
            max_workers: int = _MAX_RESOLVE_WORKERS
    ):
        self._response_queues: list = response_queues
        self._logger: logging.Logger = logger
        # Built once; reads the SSH script bundled in the package resources.
        self._package_processor = package_mains_processor.PackageMainsProcessor(
            script_file_stem=ssh_script_to_execute)
        self._clients: dict[str, SSHRemote] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._dict_lock = threading.Lock()              # guards get-or-create of _clients/_locks
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix='ssh_broker')

    def _host_lock(self, ip: str) -> threading.Lock:
        with self._dict_lock:
            lock = self._locks.get(ip)
            if lock is None:
                lock = threading.Lock()
                self._locks[ip] = lock
            return lock

    def _get_or_create_client(self, ip: str, ssh_user: str, ssh_pass: str) -> SSHRemote:
        with self._dict_lock:
            client = self._clients.get(ip)
            if client is None:
                client = SSHRemote(ip, ssh_user, ssh_pass, logger=self._logger)
                self._clients[ip] = client
            return client

    def _forget_client(self, ip: str) -> None:
        """Drop a host's connection so the next request for it reconnects fresh."""
        with self._dict_lock:
            client = self._clients.pop(ip, None)
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

    def _handle(self, worker_id, request_id, source_ip, source_port, ssh_user, ssh_pass) -> None:
        """Resolve one request and ALWAYS send exactly one response back."""
        try:
            host_lock = self._host_lock(source_ip)
            with host_lock:                             # serialize this host's single connection
                client = self._get_or_create_client(source_ip, ssh_user, ssh_pass)
                try:
                    result = self._run_lookup(client, source_ip, source_port)
                except Exception as e:
                    result = f"SSH lookup error: {e}"
                    self._forget_client(source_ip)
        except Exception as e:
            # Any unexpected failure still owes the caller a response.
            result = f"SSH broker error: {e}"
        finally:
            try:
                self._response_queues[worker_id].put((request_id, result))
            except Exception:
                pass                                    # response queue gone; nothing more to do

    def serve_forever(self, request_queue) -> None:
        """Dispatch loop: block on request_queue, submit each request; stop on the None sentinel."""
        try:
            while True:
                msg = request_queue.get()
                if msg is None:
                    break
                self._executor.submit(self._handle, *msg)
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """Stop the pool and close every cached connection (best-effort)."""
        self._executor.shutdown(wait=False)
        with self._dict_lock:
            hosts = list(self._clients.keys())
        for ip in hosts:
            self._forget_client(ip)


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

import os
import time
import queue
import threading
from pathlib import Path
from typing import Optional, Union, Dict, Any, List
import xml.etree.ElementTree as Et
import binascii

import pywintypes
import win32api
import win32event
import win32evtlog
import winerror


# ---------------------------
# Generic XML parsing helpers
# ---------------------------

def _strip_ns(tag: str) -> str:
    """Strip XML namespace from tag name."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _element_to_obj(elem: Et.Element) -> Any:
    """
    Convert an ElementTree element into a JSON-serializable object.

    Rules:
      - Attributes go under "@attrs" if present.
      - Non-empty text goes under "#text" when element also has attrs/children.
      - Child elements are grouped by tag; repeated tags become lists.
      - If element is a leaf with only text and no attrs -> returns text.
      - If element is a leaf with attrs but no children -> returns dict with attrs (+ text if any).
    """
    tag_name = _strip_ns(elem.tag)

    # Collect children
    children = list(elem)
    attrs = dict(elem.attrib) if elem.attrib else {}
    text = (elem.text or "").strip()

    if not children:
        # Leaf node
        if attrs:
            out: Dict[str, Any] = {"@attrs": attrs}
            if text:
                out["#text"] = text
            return out
        return text if text else None

    # Node with children
    out: Dict[str, Any] = {}
    if attrs:
        out["@attrs"] = attrs
    if text:
        out["#text"] = text

    grouped: Dict[str, List[Any]] = {}
    for child in children:
        ctag = _strip_ns(child.tag)
        grouped.setdefault(ctag, []).append(_element_to_obj(child))

    # Promote singletons
    for k, v in grouped.items():
        out[k] = v[0] if len(v) == 1 else v

    # Wrap with the element tag at top-level to preserve structure
    return {tag_name: out}


def parse_event_xml(xml_text: str) -> Dict[str, Any]:
    """
    General-purpose Windows Event Log XML parser.

    Produces:
      - system: normalized key fields from <System> (when present)
      - event_data: list of key/value pairs from <EventData> (when present)
      - user_data: nested object from <UserData> (when present)
      - raw_tree: full XML converted to a nested dict (best-effort)

    This parser is event-id/provider agnostic. It parses "everything" by including raw_tree.
    """
    try:
        root = Et.fromstring(xml_text)
    except Exception as e:
        return {
            "parse_error": f"{type(e).__name__}: {e}",
            "xml": xml_text,
        }

    def _find(path: str) -> Optional[Et.Element]:
        # Namespace-agnostic searches via {*} wildcard.
        return root.find(path)

    def _get_text(elem: Optional[Et.Element]) -> Optional[str]:
        if elem is None:
            return None
        t = (elem.text or "").strip()
        return t if t else None

    system_elem = _find("./{*}System")
    event_data_elem = _find("./{*}EventData")
    user_data_elem = _find("./{*}UserData")

    system: Dict[str, Any] = {}
    if system_elem is not None:
        provider = system_elem.find("./{*}Provider")
        time_created = system_elem.find("./{*}TimeCreated")
        correlation = system_elem.find("./{*}Correlation")
        execution = system_elem.find("./{*}Execution")
        security = system_elem.find("./{*}Security")

        system = {
            "provider": {
                "name": provider.attrib.get("Name") if provider is not None else None,
                "guid": provider.attrib.get("Guid") if provider is not None else None,
                "event_source_name": provider.attrib.get("EventSourceName") if provider is not None else None,
            },
            "event_id": _get_text(system_elem.find("./{*}EventID")),
            "version": _get_text(system_elem.find("./{*}Version")),
            "level": _get_text(system_elem.find("./{*}Level")),
            "task": _get_text(system_elem.find("./{*}Task")),
            "opcode": _get_text(system_elem.find("./{*}Opcode")),
            "keywords": _get_text(system_elem.find("./{*}Keywords")),
            "time_created": {
                "system_time": time_created.attrib.get("SystemTime") if time_created is not None else None
            },
            "event_record_id": _get_text(system_elem.find("./{*}EventRecordID")),
            "correlation": dict(correlation.attrib) if correlation is not None and correlation.attrib else None,
            "execution": dict(execution.attrib) if execution is not None and execution.attrib else None,
            "channel": _get_text(system_elem.find("./{*}Channel")),
            "computer": _get_text(system_elem.find("./{*}Computer")),
            "security": dict(security.attrib) if security is not None and security.attrib else None,
        }

    if event_data_elem is not None:
        data_dict: Dict[str, Any] = {}
        unnamed: List[Any] = []

        def _put(dct: Dict[str, Any], key: str, val: Any) -> None:
            # If a name repeats, preserve all values as a list.
            if key in dct:
                existing = dct[key]
                if isinstance(existing, list):
                    existing.append(val)
                else:
                    dct[key] = [existing, val]
            else:
                dct[key] = val

        def _try_hex_to_int(val: Any) -> Optional[int]:
            if not isinstance(val, str):
                return None
            s = val.strip()
            if len(s) > 2 and (s.startswith("0x") or s.startswith("0X")):
                try:
                    return int(s, 16)
                except ValueError:
                    return None
            return None

        for d in event_data_elem.findall("./{*}Data"):
            name = d.attrib.get("Name")
            val = (d.text or "").strip()
            value = val if val else None

            if name:
                _put(data_dict, name, value)

                int_value = _try_hex_to_int(value)
                if int_value is not None:
                    _put(data_dict, f"{name}Int", int_value)
            else:
                unnamed.append(value)

        # If there are <Data> elements without Name, keep them under a reserved key.
        if unnamed:
            data_dict["__unnamed__"] = unnamed

        event_data = data_dict

    user_data: Optional[Dict[str, Any]] = None
    if user_data_elem is not None:
        # UserData usually contains one child node with nested structure.
        # Convert the whole subtree for completeness.
        user_data = _element_to_obj(user_data_elem)  # type: ignore[assignment]

    raw_tree = _element_to_obj(root)

    return {
        "system": system if system else None,
        "event_data": event_data,
        "user_data": user_data,
        "raw_tree": raw_tree,
    }


# ---------------------------
# Subscription / bookmark logic
# ---------------------------


def _safe_evt_close(handle) -> None:
    try:
        if handle:
            win32evtlog.EvtClose(handle)
    except Exception:
        pass


def load_bookmark(bookmark_path: Path):
    """Load an Evt bookmark handle from an XML file, or create an empty bookmark if missing/invalid."""
    try:
        if bookmark_path.exists():
            xml = bookmark_path.read_text(encoding="utf-8").strip()
            if xml:
                return win32evtlog.EvtCreateBookmark(xml)
    except pywintypes.error:
        pass
    return win32evtlog.EvtCreateBookmark(None)


def save_bookmark(bookmark_handle, bookmark_path: Path) -> None:
    """Persist an Evt bookmark handle to an XML file (atomic replace on same volume)."""
    xml = win32evtlog.EvtRender(bookmark_handle, win32evtlog.EvtRenderBookmark)

    bookmark_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = bookmark_path.with_suffix(bookmark_path.suffix + ".tmp")
    tmp.write_text(xml, encoding="utf-8")
    os.replace(tmp, bookmark_path)


def open_remote_session(
    server: str,
    user: Optional[str],
    domain: Optional[str],
    password: Optional[str],
):
    """
    Open a remote Event Log session via RPC.
    If you want to use current credentials, pass None for user/domain/password.
    """
    login = (server, user, domain, password, win32evtlog.EvtRpcLoginAuthDefault)
    # noinspection PyTypeChecker
    return win32evtlog.EvtOpenSession(login, win32evtlog.EvtRpcLogin, 0, 0)


def build_xpath_query(
        event_id: Optional[str] = None,
        provider: Optional[str] = None
) -> str:
    """Build the XPath query used by EvtSubscribe."""
    if (event_id is None) == (provider is None):
        raise ValueError("You must specify exactly one of event_id or provider.")

    if provider:
        return f"*[System/Provider[@Name='{provider}']]"

    return f"*[System[(EventID={event_id})]]"


class EventLogSubscriber:
    """
    Minimal subscriber module.

    Public API:
      - start()
      - stop()
      - emit(timeout=None)  -> returns dict: {"xml": "<Event .../>"}

    Uses:
      - optional remote session (EvtOpenSession)
      - subscription (EvtSubscribe)
      - polling (EvtNext)
      - bookmark update + periodic bookmark flush
    """

    def __init__(
            self,
            log_channel: str,
            event_id: int = None,
            provider: str = None,
            server: Optional[str] = None,
            user: Optional[str] = None,
            domain: Optional[str] = None,
            password: Optional[str] = None,
            bookmark_path: Union[str, Path, None] = "bookmark.xml",
            from_oldest: bool = False,
            resume: bool = False,
            flush_every_seconds: int = 5,
            batch_size: int = 32,
            poll_timeout_ms: int = 1000,
            queue_maxsize: int = 0,
            parse_xml: bool = True,
    ):
        """
        Create an Event Log subscription reader with a small pull-based API.

        The subscriber runs in a background thread after `start()` and yields events via `emit()`.
        Each emitted item is a dict:
            {"xml": "<Event .../>", "event": <parsed dict>}   (if parse_xml=True)
            {"xml": "<Event .../>"}                          (if parse_xml=False)

        Args:
            log_channel:
                Windows Event Log channel name (local or remote), e.g. "Security", "System", "Application".
                Example:
                    EventLogSubscriber(log_channel="Security", event_id=4688)

            event_id:
                Subscribe only to a specific EventID in the channel (mutually exclusive with `provider`).
                Example:
                    EventLogSubscriber(log_channel="Security", event_id=4688)

            provider:
                Subscribe only to a specific Provider Name in the channel (mutually exclusive with `event_id`).
                Example:
                    EventLogSubscriber(log_channel="System", provider="Service Control Manager")

            server:
                Remote host to connect to (enables RPC session via EvtOpenSession).
                Use None to subscribe locally.
                Example (remote):
                    EventLogSubscriber(
                        log_channel="Security",
                        event_id=4688,
                        server="WIN-SERVER-01",
                        user="Administrator",
                        domain="CONTOSO",
                        password="***",
                    )
                Example (local):
                    EventLogSubscriber(log_channel="Security", event_id=4688, server=None)

            user:
                Remote username for RPC login. If None (and server is set), Windows will attempt current credentials.
                Example:
                    EventLogSubscriber(log_channel="Security", event_id=4688, server="WIN-SERVER-01", user="svc_evt")

            domain:
                Remote domain for RPC login (often AD domain). Use None for local machine accounts.
                Example:
                    EventLogSubscriber(
                        log_channel="Security",
                        event_id=4688,
                        server="WIN-SERVER-01",
                        user="svc_evt",
                        domain="CONTOSO",
                        password="***",
                    )

            password:
                Remote password for RPC login. If you pass user/domain, you typically pass password as well.
                Example:
                    EventLogSubscriber(
                        log_channel="Security",
                        event_id=4688,
                        server="WIN-SERVER-01",
                        user="svc_evt",
                        domain="CONTOSO",
                        password="***",
                    )

            bookmark_path:
                Where to store the bookmark XML (used with `resume=True` and for periodic persistence).
                Set to None to disable bookmark persistence entirely.
                Examples:
                    EventLogSubscriber(log_channel="Security", event_id=4688, bookmark_path="bookmark_4688.xml", resume=True)
                    EventLogSubscriber(log_channel="Security", event_id=4688, bookmark_path=None)  # no persistence

            from_oldest:
                If True, start reading from the oldest record in the channel (ignores bookmark semantics for start position).
                Example:
                    EventLogSubscriber(log_channel="Security", event_id=4688, from_oldest=True)

            resume:
                If True and bookmark exists, resume after the saved bookmark (StartAfterBookmark).
                If True and bookmark does not exist, starts from future events (ToFutureEvents) until bookmark is created.
                Example:
                    EventLogSubscriber(log_channel="Security", event_id=4688, bookmark_path="bookmark.xml", resume=True)

            flush_every_seconds:
                How often to flush the bookmark to disk (lower => more durability; higher => less I/O).
                Example:
                    EventLogSubscriber(log_channel="Security", event_id=4688, flush_every_seconds=1)

            batch_size:
                Maximum number of events to pull per EvtNext call (higher => more throughput; too high can increase latency).
                Example:
                    EventLogSubscriber(log_channel="Security", event_id=4688, batch_size=128)

            poll_timeout_ms:
                Timeout passed to EvtNext (in milliseconds). Lower values generally make `stop()` respond faster,
                but can increase CPU wakeups.
                Example:
                    EventLogSubscriber(log_channel="Security", event_id=4688, poll_timeout_ms=250)

            queue_maxsize:
                Max in-memory queue size for events waiting to be consumed by `emit()`.
                0 means "unbounded". A bounded queue applies backpressure (producer waits when full).
                Examples:
                    EventLogSubscriber(log_channel="Security", event_id=4688, queue_maxsize=0)      # unbounded
                    EventLogSubscriber(log_channel="Security", event_id=4688, queue_maxsize=1000)   # bounded

            parse_xml:
                If True, `emit()` returns a parsed representation under key "event" using `parse_event_xml`.
                If False, only raw XML is returned.
                Examples:
                    EventLogSubscriber(log_channel="Security", event_id=4688, parse_xml=True)
                    EventLogSubscriber(log_channel="Security", event_id=4688, parse_xml=False)
        """

        if event_id is None and provider is None:
            raise ValueError("You must specify either an event ID or provider name to subscribe to.")
        if event_id is not None and provider is not None:
            raise ValueError("You can only subscribe by event ID or provider, not both.")

        self.log_channel = log_channel
        self.provider = provider
        self.event_id = str(event_id) if event_id is not None else None

        self.server = server
        self.user = user
        self.domain = domain
        self.password = password

        self.bookmark_path = Path(bookmark_path) if bookmark_path is not None else None
        self.from_oldest = bool(from_oldest)
        self.resume = bool(resume)
        self.flush_every_seconds = int(flush_every_seconds)
        self.batch_size = int(batch_size)
        self.poll_timeout_ms = int(poll_timeout_ms)

        self.parse_xml = bool(parse_xml)

        self._q: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=queue_maxsize)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._session_handle = None
        self._subscription_handle = None
        self._bookmark_handle = None
        self._signal_handle = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="EventLogSubscriber", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join()
            self._thread = None

    def emit(self, timeout: float = None) -> Optional[dict]:
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None

    def _put(self, item: Dict[str, Any]) -> None:
        while not self._stop_event.is_set():
            try:
                self._q.put(item, timeout=0.5)
                return
            except queue.Full:
                continue

    @staticmethod
    def _parse_event_xml(event_xml: str) -> Dict[str, Any]:
        """
        Parse the given event XML string into a dictionary.

        :param event_xml: The XML string of the event.
        :return: A dictionary containing parsed event data.
        """

        try:
            result = parse_event_xml(event_xml)
        except Et.ParseError as e:
            print(f"Error parsing event XML: {e}")
            result = {"parse_error": f"{type(e).__name__}: {e}"}
        except Exception as e:
            print(f"Error getting rendered message: {e}")
            result = {"parse_error": f"{type(e).__name__}: {e}"}

        return result

    def _run(self) -> None:
        bookmark_exists = False
        last_flush = time.monotonic()

        try:
            # Session (remote or local)
            if self.server:
                self._session_handle = open_remote_session(self.server, self.user, self.domain, self.password)
            else:
                self._session_handle = None

            query = build_xpath_query(event_id=self.event_id, provider=self.provider)

            # Bookmark
            if self.bookmark_path is not None:
                bookmark_exists = self.bookmark_path.exists()
                if self.resume and bookmark_exists:
                    self._bookmark_handle = load_bookmark(self.bookmark_path)
                else:
                    self._bookmark_handle = win32evtlog.EvtCreateBookmark(None)
            else:
                self._bookmark_handle = None

            # Flags
            if self.from_oldest:
                flags = win32evtlog.EvtSubscribeStartAtOldestRecord
            elif self.resume and bookmark_exists:
                flags = win32evtlog.EvtSubscribeStartAfterBookmark
            else:
                flags = win32evtlog.EvtSubscribeToFutureEvents

            bookmark_arg = self._bookmark_handle if flags == win32evtlog.EvtSubscribeStartAfterBookmark else None

            # Signal event (optional; we still poll EvtNext)
            self._signal_handle = win32event.CreateEvent(None, 0, 0, None)

            self._subscription_handle = win32evtlog.EvtSubscribe(
                self.log_channel,
                flags,
                SignalEvent=self._signal_handle,
                Query=query,
                Session=self._session_handle,
                Bookmark=bookmark_arg,
            )

            while not self._stop_event.is_set():
                try:
                    events = win32evtlog.EvtNext(
                        self._subscription_handle,
                        self.batch_size,
                        Timeout=self.poll_timeout_ms,
                    )
                except pywintypes.error as e:
                    # Idle-ish cases (pywin32 varies here)
                    if e.winerror in (
                        winerror.ERROR_TIMEOUT,          # 1460
                        winerror.ERROR_NO_MORE_ITEMS,    # 259
                        winerror.ERROR_INVALID_OPERATION # 4317
                    ):
                        self._maybe_flush_bookmark(last_flush)
                        if self.bookmark_path is not None:
                            now = time.monotonic()
                            if now - last_flush >= self.flush_every_seconds:
                                last_flush = now
                        continue
                    raise

                for evt in events:
                    try:
                        xml_string: str = win32evtlog.EvtRender(evt, win32evtlog.EvtRenderEventXml)
                        msg: Dict[str, Any] = {"xml": xml_string}

                        if self.parse_xml:
                            msg['event'] = self._parse_event_xml(xml_string)

                        self._put(msg)
                        if self._bookmark_handle is not None:
                            win32evtlog.EvtUpdateBookmark(self._bookmark_handle, evt)
                    finally:
                        _safe_evt_close(evt)

                if self.bookmark_path is not None and self._bookmark_handle is not None:
                    now = time.monotonic()
                    if now - last_flush >= self.flush_every_seconds:
                        save_bookmark(self._bookmark_handle, self.bookmark_path)
                        last_flush = now

        finally:
            # Final bookmark flush
            try:
                if self.bookmark_path is not None and self._bookmark_handle is not None:
                    save_bookmark(self._bookmark_handle, self.bookmark_path)
            except Exception:
                pass

            _safe_evt_close(self._subscription_handle)
            self._subscription_handle = None

            _safe_evt_close(self._bookmark_handle)
            self._bookmark_handle = None

            _safe_evt_close(self._session_handle)
            self._session_handle = None

            try:
                if self._signal_handle:
                    win32api.CloseHandle(self._signal_handle)
            except Exception:
                pass
            self._signal_handle = None

    def _maybe_flush_bookmark(self, last_flush: float) -> None:
        if self.bookmark_path is None or self._bookmark_handle is None:
            return
        now = time.monotonic()
        if now - last_flush >= self.flush_every_seconds:
            try:
                save_bookmark(self._bookmark_handle, self.bookmark_path)
            except Exception:
                pass

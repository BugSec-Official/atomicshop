import win32evtlog
import xml.etree.ElementTree as Et
import time
import threading
import queue
from typing import Union


class EventLogSubscriber:
    """
    Class for subscribing to Windows Event Log events.

    Usage:
        from atomicshop.wrappers.pywin32w.win_event_log import subscribe

        event_log_subscriber = subscribe.EventLogSubscriber('Security', 4688)
        event_log_subscriber.start()

        while True:
            event = event_log_subscriber.emit()
            print(event)
    """
    def __init__(self, log_channel: str, event_id: int):
        """
        :param log_channel: The name of the event log channel to subscribe to. Examples:
            Security, System, Application, etc.
        :param event_id: The ID of the event to subscribe to.
            Example: 4688 for process creation events in "Security" channel.
        """
        self.log_channel: str = log_channel
        self.event_id: str = str(event_id)

        self._event_queue = queue.Queue()
        self._subscription_thread = None

    def start(self):
        """Start the subscription process."""
        self._subscription_thread = threading.Thread(
            target=start_subscription, args=(self.log_channel, self.event_id, self._event_queue)
        )
        self._subscription_thread.daemon = True
        self._subscription_thread.start()

    def stop(self):
        """Stop the subscription process."""
        if self._subscription_thread:
            self._subscription_thread.join()
            self._subscription_thread = None

    def emit(self, timeout: float = None) -> Union[dict, None]:
        """
        Get the next event from the event queue.

        :param timeout: The maximum time (in seconds) to wait for an event.
            If None, the function will block until an event is available.
        :return: A dictionary containing the event data, or None if no event is available.
        """
        try:
            return self._event_queue.get(timeout=timeout)
        except queue.Empty:
            return None


def _parse_event_xml(event_xml):
    root = Et.fromstring(event_xml)
    data = {}
    for elem in root.iter():
        if 'Name' in elem.attrib:
            data[elem.attrib['Name']] = elem.text
    return data


def _handle_event(event, event_queue):
    event_xml = win32evtlog.EvtRender(event, win32evtlog.EvtRenderEventXml)
    try:
        data = _parse_event_xml(event_xml)
    except Et.ParseError as e:
        print(f"Error parsing event XML: {e}")
        return

    event_dict: dict = {
        'user_sid': data.get("SubjectUserSid", "Unknown"),
        'user_name': data.get("SubjectUserName", "Unknown"),
        'domain': data.get("SubjectDomainName", "Unknown"),
        'pid_hex': data.get("NewProcessId", "0"),
        'process_name': data.get("NewProcessName", "Unknown"),
        'command_line': data.get("CommandLine", None),
        'parent_pid_hex': data.get("ProcessId", "0"),
        'parent_process_name': data.get("ParentProcessName", "Unknown")
    }

    try:
        process_id = int(event_dict['pid_hex'], 16)
    except ValueError:
        process_id = "Unknown"

    try:
        parent_pid = int(event_dict['parent_pid_hex'], 16)
    except ValueError:
        parent_pid = "Unknown"

    event_dict['pid'] = process_id
    event_dict['parent_pid'] = parent_pid

    # if user_sid != "Unknown":
    #     try:
    #         user_name, domain, type = win32security.LookupAccountSid(None, user_sid)
    #     except Exception as e:
    #         print(f"Error looking up account SID: {e}")

    event_queue.put(event_dict)


def _event_callback(action, context, event):
    event_queue = context['event_queue']
    if action == win32evtlog.EvtSubscribeActionDeliver:
        _handle_event(event, event_queue)


def start_subscription(log_channel: str, event_id: int, event_queue):
    """
    Start listening for events in the specified log channel with the given event ID.

    :param log_channel: The name of the event log channel to subscribe to. Examples:
        Security, System, Application, etc.
    :param event_id: The ID of the event to subscribe to.
        Example: 4688 for process creation events in "Security" channel.
    :param event_queue: A queue to store the received events
    """
    # This selects the System node within each event.
    # The System node contains metadata about the event, such as the event ID, provider name, timestamp, and more.
    query = f"*[System/EventID={str(event_id)}]"

    subscription = win32evtlog.EvtSubscribe(
        log_channel,
        win32evtlog.EvtSubscribeToFutureEvents,
        SignalEvent=None,
        Query=query,
        Callback=_event_callback,
        Context={'event_queue': event_queue}
    )

    print("Listening for new process creation events...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopped listening for events.")

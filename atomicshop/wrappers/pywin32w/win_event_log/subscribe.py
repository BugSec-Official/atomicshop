import win32evtlog
import xml.etree.ElementTree as Et
import time
import threading
import queue
from typing import Union
import binascii


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
    def __init__(self, log_channel: str, event_id: int = None, provider: str = None):
        """
        :param log_channel: The name of the event log channel to subscribe to. Examples:
            Security, System, Application, etc.
        :param event_id: The ID of the event to subscribe to.
            Example: 4688 for process creation events in "Security" channel.
            You can only subscribe by event ID or provider, not both.
        :param provider: The name of the provider to subscribe to.
            You can only subscribe by event ID or provider, not both.
        """

        if event_id is None and provider is None:
            raise ValueError("You must specify either an event ID or provider name to subscribe to.")
        elif event_id and provider:
            raise ValueError("You can only subscribe by event ID or provider, not both.")

        self.log_channel: str = log_channel
        self.provider: str = provider

        if event_id:
            self.event_id: str = str(event_id)
        else:
            self.event_id = event_id

        self._event_queue = queue.Queue()
        self._subscription_thread = None

    def start(self):
        """Start the subscription process."""
        self._subscription_thread = threading.Thread(
            target=start_subscription, args=(self.log_channel, self._event_queue, self.event_id, self.provider)
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

    # Helper function to strip namespace
    def strip_namespace(tag):
        return tag.split('}')[-1]  # Remove namespace

    # Iterate over all elements
    for elem in root.iter():
        # Extract elements with text content
        if elem.text and elem.text.strip():
            tag = elem.tag.split('}')[-1]  # Remove namespace
            data[tag] = elem.text.strip()

        # Extract elements with attributes
        for attr_name, attr_value in elem.attrib.items():
            tag = elem.tag.split('}')[-1]  # Remove namespace
            data[f"{tag}_{attr_name}"] = attr_value

        # Handle Binary data
        if elem.tag.split('}')[-1] == 'Binary':
            try:
                data['BinaryReadable'] = binascii.unhexlify(elem.text.strip())
            except (TypeError, binascii.Error) as e:
                print(f"Error decoding binary data: {e}")
                data['BinaryReadable'] = elem.text.strip()

    # Extract system-specific data
    system_data = root.find(".//{http://schemas.microsoft.com/win/2004/08/events/event}System")
    if system_data is not None:
        for system_elem in system_data:
            tag = strip_namespace(system_elem.tag)
            if system_elem.attrib:
                for attr_name, attr_value in system_elem.attrib.items():
                    data[f"{tag}_{attr_name}"] = attr_value
            if system_elem.text and system_elem.text.strip():
                data[tag] = system_elem.text.strip()

    # Extract event-specific data
    event_data = root.find(".//{http://schemas.microsoft.com/win/2004/08/events/event}EventData")
    if event_data is not None:
        for data_elem in event_data:
            if strip_namespace(data_elem.tag) == 'Data' and 'Name' in data_elem.attrib:
                data[data_elem.attrib['Name']] = data_elem.text.strip()

    # Extract user data if available
    user_data = root.find(".//{http://schemas.microsoft.com/win/2004/08/events/event}UserData")
    if user_data is not None:
        for user_elem in user_data:
            tag = strip_namespace(user_elem.tag)
            if user_elem.attrib:
                for attr_name, attr_value in user_elem.attrib.items():
                    data[f"{tag}_{attr_name}"] = attr_value
            if user_elem.text and user_elem.text.strip():
                data[tag] = user_elem.text.strip()

    # Extract rendering info (additional details like the message)
    rendering_info = root.find(".//{http://schemas.microsoft.com/win/2004/08/events/event}RenderingInfo")
    if rendering_info is not None:
        for info_elem in rendering_info:
            tag = strip_namespace(info_elem.tag)
            if info_elem.text and info_elem.text.strip():
                data[f"RenderingInfo_{tag}"] = info_elem.text.strip()

    return data


def _handle_event(event, event_queue):
    # Render event as XML
    event_xml = win32evtlog.EvtRender(event, win32evtlog.EvtRenderEventXml)
    data = None
    try:
        data = _parse_event_xml(event_xml)
    except Et.ParseError as e:
        print(f"Error parsing event XML: {e}")
    except Exception as e:
        print(f"Error getting rendered message: {e}")

    event_queue.put(data)


def _event_callback(action, context, event):
    event_queue = context['event_queue']
    if action == win32evtlog.EvtSubscribeActionDeliver:
        _handle_event(event, event_queue)


def start_subscription(
        log_channel: str,
        event_queue,
        event_id: str = None,
        provider: str = None
):
    """
    Start listening for events in the specified log channel with the given event ID.

    :param log_channel: The name of the event log channel to subscribe to. Examples:
        Security, System, Application, etc.
    :param event_queue: A queue to store the received events
    :param event_id: The ID of the event to subscribe to.
        Example: 4688 for process creation events in "Security" channel.
        You can only subscribe by event ID or provider, not both.
    :param provider: The name of the provider to subscribe to.
        You can only subscribe by event ID or provider, not both.
    """

    if event_id is None and provider is None:
        raise ValueError("You must specify either an event ID or provider name to subscribe to.")
    elif event_id and provider:
        raise ValueError("You can only subscribe by event ID or provider, not both.")

    # This selects the System node within each event.
    # The System node contains metadata about the event, such as the event ID, provider name, timestamp, and more.
    xpath_query = None
    if provider:
        xpath_query = f"*[System/Provider[@Name='{provider}']]"
    elif event_id:
        xpath_query = f"*[System/EventID={event_id}]"

    subscription = win32evtlog.EvtSubscribe(
        log_channel,
        win32evtlog.EvtSubscribeToFutureEvents,
        SignalEvent=None,
        Query=xpath_query,
        Callback=_event_callback,
        Context={'event_queue': event_queue}
    )

    print("Listening for new process creation events...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopped listening for events.")

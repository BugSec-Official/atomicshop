from .. import subscribe
from .... import win_auditw


LOG_CHANNEL: str = 'Security'
EVENT_ID: int = 4688


class ProcessCreateSubscriber(subscribe.EventLogSubscriber):
    """
    Class for subscribing to Windows Event Log events related to process creation.

    Usage:
        from atomicshop.wrappers.pywin32w.win_event_log.subscribes import process_create

        process_create_subscriber = process_create.ProcessCreateSubscriber()
        process_create_subscriber.start()

        while True:
            event = process_create_subscriber.emit()
            print(event)
    """
    def __init__(self):
        super().__init__(log_channel=LOG_CHANNEL, event_id=EVENT_ID)

    def start(self):
        """Start the subscription process."""
        win_auditw.enable_audit_process_creation()
        win_auditw.enable_command_line_auditing()

        super().start()

    def stop(self):
        """Stop the subscription process."""
        super().stop()

    def emit(self, timeout: float = None) -> dict:
        """
        Get the next event from the event queue.

        :param timeout: The maximum time (in seconds) to wait for an event.
            If None, the function will block until an event is available.
        :return: A dictionary containing the event data.
        """

        data = super().emit(timeout=timeout)

        data['NewProcessIdInt'] = int(data['NewProcessId'], 16)
        data['ParentProcessIdInt'] = int(data['ProcessId'], 16)

        # if user_sid != "Unknown":
        #     try:
        #         user_name, domain, type = win32security.LookupAccountSid(None, user_sid)
        #     except Exception as e:
        #         print(f"Error looking up account SID: {e}")

        return data

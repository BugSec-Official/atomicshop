from .. import subscribe
from .... import win_auditw


LOG_CHANNEL: str = 'Security'
EVENT_ID: int = 4689


class ProcessTerminateSubscriber(subscribe.EventLogSubscriber):
    """
    Class for subscribing to Windows Event Log events related to process termination.

    Usage:
        from atomicshop.wrappers.pywin32w.win_event_log.subscribes import process_terminate

        process_terminate_subscriber = process_terminate.ProcessTerminateSubscriber()
        process_terminate_subscriber.start()

        while True:
            event = process_terminate_subscriber.emit()
            print(event)
    """
    def __init__(self):
        super().__init__(log_channel=LOG_CHANNEL, event_id=EVENT_ID)

    def start(self):
        """Start the subscription process."""
        win_auditw.enable_audit_process_termination()

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

        data['ProcessIdInt'] = int(data['ProcessId'], 16)

        return data
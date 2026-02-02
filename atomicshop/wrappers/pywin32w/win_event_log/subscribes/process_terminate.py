from typing import Optional, Dict, Any

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

    def __init__(
            self,
            server: Optional[str] = None,
            user: Optional[str] = None,
            domain: Optional[str] = None,
            password: Optional[str] = None,
            bookmark_path: str = "bookmark_security_4689.xml",
            resume: bool = True,
            from_oldest: bool = False,
    ):
        super().__init__(
            subscriptions=[(LOG_CHANNEL, [EVENT_ID])],
            server=server,
            user=user,
            domain=domain,
            password=password,
            bookmark_path=bookmark_path,
            resume=resume,
            from_oldest=from_oldest,
        )

    def start(self):
        """Start the subscription process."""
        # Enable audit policy for process termination events if not connected to a remote server.
        if not self.server:
            win_auditw.enable_audit_process_termination()

        super().start()

    def stop(self):
        """Stop the subscription process."""
        super().stop()

    def emit(self, timeout: float = None) -> Optional[Dict[str, Any]]:
        """
        Get the next event from the event queue.

        :param timeout: The maximum time (in seconds) to wait for an event.
            If None, the function will block until an event is available.
        :return: A dictionary containing the event data.
        """

        return super().emit(timeout=timeout)

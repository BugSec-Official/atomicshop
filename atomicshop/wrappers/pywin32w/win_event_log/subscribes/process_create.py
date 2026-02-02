from typing import Optional, Dict, Any

from .. import subscribe
from .... import win_auditw


LOG_CHANNEL: str = 'Security'
EVENT_ID: int = 4688


class ProcessCreationSubscriber(subscribe.EventLogSubscriber):
    """
    Process creation specific module.
    Wraps EventLogSubscriber configured for Security/4688 and exposes:
      - start()
      - stop()
      - emit(timeout=None) -> parsed dict (not raw xml)
    """

    def __init__(
        self,
        server: Optional[str] = None,
        user: Optional[str] = None,
        domain: Optional[str] = None,
        password: Optional[str] = None,
        bookmark_path: str = "bookmark_security_4688.xml",
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

    def start(self) -> None:
        # Enable auditing only if local server.
        if self.server is None:
            win_auditw.enable_audit_process_creation()
            win_auditw.enable_command_line_auditing()

        super().start()

    def stop(self) -> None:
        super().stop()

    def emit(self, timeout: float = None) -> Optional[Dict[str, Any]]:
        return super().emit(timeout=timeout)
from typing import Optional, Dict, Any

from .. import subscribe


LOG_CHANNEL: str = 'Application'
EVENT_ID: int = 1000
# Optional also 1001 for process crash with dump by WERmgr (if WER is enabled), but it has fewer details.


class ProcessCrashSubscriber(subscribe.EventLogSubscriber):
    """
    Process crash specific module.
    Wraps EventLogSubscriber configured for Security/1000 and exposes:
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
        bookmark_path: str = "bookmark_application_1000.xml",
        resume: bool = True,
        from_oldest: bool = False,
    ):
        super().__init__(
            log_channel=LOG_CHANNEL,
            event_id=EVENT_ID,
            server=server,
            user=user,
            domain=domain,
            password=password,
            bookmark_path=bookmark_path,
            resume=resume,
            from_oldest=from_oldest,
        )

    def start(self) -> None:
        super().start()

    def stop(self) -> None:
        super().stop()

    def emit(self, timeout: float = None) -> Optional[Dict[str, Any]]:
        return super().emit(timeout=timeout)
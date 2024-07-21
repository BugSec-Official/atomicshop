import winreg
import sys

from .. import subscribe
from .....print_api import print_api


SCHANNEL_LOGGING_REG_PATH: str = r'SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL'
SCHANNEL_EVENT_LOGGING_KEY: str = 'EventLogging'
LOG_CHANNEL: str = 'System'
PROVIDER: str = 'Schannel'


class SchannelLoggingSubscriber(subscribe.EventLogSubscriber):
    """
    Class for subscribing to Windows Event Log events related to process creation.

    Usage:
        from atomicshop.wrappers.pywin32w.win_event_log.subscribes import schannel_logging

        process_create_subscriber = schannel_logging.SchannelLoggingSubscriber()
        process_create_subscriber.start()

        while True:
            event = process_create_subscriber.emit()
            print(event)
    """
    def __init__(self):
        super().__init__(log_channel=LOG_CHANNEL, provider=PROVIDER)

    def start(self):
        """Start the subscription process."""
        enable_schannel_logging()

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
        return super().emit(timeout=timeout)


def enable_schannel_logging(logging_value: int = 1, print_kwargs: dict = None):
    """
    Value 	Description
    0x0000 	Do not log
    0x0001 	Log error messages
    0x0002 	Log warnings
    0x0003 	Log warnings and error messages
    0x0004 	Log informational and success events
    0x0005 	Log informational, success events and error messages
    0x0006 	Log informational, success events and warnings
    0x0007 	Log informational, success events, warnings, and error messages (all log levels)
    """

    if is_schannel_logging_enabled(logging_value):
        print_api(
            "Schannel event logging is already enabled.", color='yellow',
            **(print_kwargs or {}))
        return

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, SCHANNEL_LOGGING_REG_PATH, 0, winreg.KEY_ALL_ACCESS) as key:
            winreg.SetValueEx(key, SCHANNEL_EVENT_LOGGING_KEY, 0, winreg.REG_DWORD, logging_value)

        print_api(
            "Successfully enabled Schannel logging.",
            color='green', **(print_kwargs or {}))
        print_api(
            "Please restart the computer for the changes to take effect.",
            color='yellow', **(print_kwargs or {}))
        sys.exit()
    except WindowsError as e:
        print_api(
            f"Failed to enable Schannel event logging: {e}", error_type=True,
            color='red', **(print_kwargs or {}))


def is_schannel_logging_enabled(logging_value: int) -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, SCHANNEL_LOGGING_REG_PATH, 0, winreg.KEY_READ) as key:
            value, regtype = winreg.QueryValueEx(key, SCHANNEL_EVENT_LOGGING_KEY)
            return value == logging_value
    except FileNotFoundError:
        return False
    except WindowsError as e:
        print(f"Failed to read the Schannel event logging setting: {e}")
        return False

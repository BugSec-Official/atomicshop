import subprocess
import winreg

from .. import subscribe
from .....print_api import print_api


AUDITING_REG_PATH: str = r"Software\Microsoft\Windows\CurrentVersion\Policies\System\Audit"
PROCESS_CREATION_INCLUDE_CMDLINE_VALUE: str = "ProcessCreationIncludeCmdLine_Enabled"
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
        enable_audit_process_creation()
        enable_command_line_auditing()

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


def enable_audit_process_creation(print_kwargs: dict = None):
    """
    Enable the 'Audit Process Creation' policy.

    :param print_kwargs: Optional keyword arguments for the print function.
    """
    if is_audit_process_creation_enabled():
        print_api("Audit Process Creation is already enabled.", color='blue', **(print_kwargs or {}))
        return

    # Enable "Audit Process Creation" policy
    audit_policy_command = [
        "auditpol", "/set", "/subcategory:Process Creation", "/success:enable", "/failure:enable"
    ]
    try:
        subprocess.run(audit_policy_command, check=True)
        print_api("Successfully enabled 'Audit Process Creation'.", color='green', **(print_kwargs or {}))
    except subprocess.CalledProcessError as e:
        print_api(f"Failed to enable 'Audit Process Creation': {e}", error_type=True, color='red', **(print_kwargs or {}))
        raise e


def is_audit_process_creation_enabled(print_kwargs: dict = None) -> bool:
    """
    Check if the 'Audit Process Creation' policy is enabled.

    :param print_kwargs: Optional keyword arguments for the print function.
    """
    # Command to check the "Audit Process Creation" policy
    audit_policy_check_command = [
        "auditpol", "/get", "/subcategory:Process Creation"
    ]
    try:
        result = subprocess.run(audit_policy_check_command, check=True, capture_output=True, text=True)
        output = result.stdout
        # print_api(output)  # Print the output for inspection

        if "Process Creation" in output and "Success and Failure" in output:
            # print_api(
            #     "'Audit Process Creation' is enabled for both success and failure.",
            #     color='green', **(print_kwargs or {}))
            return True
        else:
            # print_api(output, **(print_kwargs or {}))
            # print_api(
            #     "'Audit Process Creation' is not fully enabled. Check the output above for details.",
            #     color='yellow', **(print_kwargs or {}))
            return False
    except subprocess.CalledProcessError as e:
        print_api(f"Failed to check 'Audit Process Creation': {e}", color='red', error_type=True, **(print_kwargs or {}))
        return False


def enable_command_line_auditing(print_kwargs: dict = None):
    """
    Enable the 'Include command line in process creation events' policy.

    :param print_kwargs: Optional keyword arguments for the print function.
    """

    if is_command_line_auditing_enabled():
        print_api(
            "[Include command line in process creation events] is already enabled.", color='blue',
            **(print_kwargs or {}))
        return

    try:
        # Open the registry key
        with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, AUDITING_REG_PATH) as reg_key:
            # Set the value
            winreg.SetValueEx(reg_key, PROCESS_CREATION_INCLUDE_CMDLINE_VALUE, 0, winreg.REG_DWORD, 1)

        print_api(
            "Successfully enabled [Include command line in process creation events].",
            color='green', **(print_kwargs or {}))
    except WindowsError as e:
        print_api(
            f"Failed to enable [Include command line in process creation events]: {e}", error_type=True,
            color='red', **(print_kwargs or {}))


def is_command_line_auditing_enabled():
    try:
        # Open the registry key
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, AUDITING_REG_PATH, 0, winreg.KEY_READ) as reg_key:
            # Query the value
            value, reg_type = winreg.QueryValueEx(reg_key, PROCESS_CREATION_INCLUDE_CMDLINE_VALUE)
            # Check if the value is 1 (enabled)
            return value == 1
    except FileNotFoundError:
        # Key or value not found, assume it's not enabled
        return False
    except WindowsError as e:
        print(f"Failed to read the 'Include command line in process creation events' setting: {e}")
        return False

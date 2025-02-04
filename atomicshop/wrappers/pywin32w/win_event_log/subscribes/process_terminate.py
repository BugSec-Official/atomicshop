import subprocess

from .. import subscribe
from .....print_api import print_api


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
        enable_audit_process_termination()

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


def enable_audit_process_termination(print_kwargs: dict = None):
    """
    Enable the 'Audit Process Termination' policy.

    :param print_kwargs: Optional keyword arguments for the print function.
    """
    if is_audit_process_termination_enabled():
        print_api("Audit Process Termination is already enabled.", color='blue', **(print_kwargs or {}))
        return

    audit_policy_command = [
        "auditpol", "/set", "/subcategory:Process Termination", "/success:enable", "/failure:enable"
    ]
    try:
        subprocess.run(audit_policy_command, check=True)
        print_api("Successfully enabled 'Audit Process Termination'.", color='green', **(print_kwargs or {}))
    except subprocess.CalledProcessError as e:
        print_api(f"Failed to enable 'Audit Process Termination': {e}", error_type=True, color='red', **(print_kwargs or {}))
        raise e


def is_audit_process_termination_enabled(print_kwargs: dict = None) -> bool:
    """
    Check if the 'Audit Process Termination' policy is enabled.

    :param print_kwargs: Optional keyword arguments for the print function.
    """
    # Command to check the "Audit Process Creation" policy
    audit_policy_check_command = [
        "auditpol", "/get", "/subcategory:Process Termination"
    ]
    try:
        result = subprocess.run(audit_policy_check_command, check=True, capture_output=True, text=True)
        output = result.stdout
        # print_api(output)  # Print the output for inspection

        if "Process Termination" in output and "Success and Failure" in output:
            # print_api(
            #     "'Audit Process Termination' is enabled for both success and failure.",
            #     color='green', **(print_kwargs or {}))
            return True
        else:
            # print_api(output, **(print_kwargs or {}))
            # print_api(
            #     "'Audit Process Termination' is not fully enabled. Check the output above for details.",
            #     color='yellow', **(print_kwargs or {}))
            return False
    except subprocess.CalledProcessError as e:
        print_api(f"Failed to check 'Audit Process Termination': {e}", color='red', error_type=True, **(print_kwargs or {}))
        return False

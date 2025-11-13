import subprocess
import winreg

from ..print_api import print_api


AUDITING_REG_PATH: str = r"Software\Microsoft\Windows\CurrentVersion\Policies\System\Audit"
PROCESS_CREATION_INCLUDE_CMDLINE_VALUE: str = "ProcessCreationIncludeCmdLine_Enabled"


def enable_command_line_auditing(print_kwargs: dict = None):
    """
    Enable the 'Include command line in process creation events' policy.

    reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System\Audit" /v ProcessCreationIncludeCmdLine_Enabled /t REG_DWORD /d 1 /f

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


def enable_audit_process_creation(print_kwargs: dict = None):
    """
    Enable the 'Audit Process Creation' policy.
    Log: Security
    Event ID: 4688 - A new process has been created.

    auditpol /set /subcategory:"Process Creation" /success:enable /failure:enable

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


def enable_audit_filtering_platform_connection(print_kwargs: dict = None):
    """
    Enable the 'Filtering Platform Connection' policy.
    This enables you to fetch connection creations and deletions from the Windows Security Event Log.
    Log: Security
    Event IDs:
        5156 - The Windows Filtering Platform has permitted a connection.
        5158 - The Windows Filtering Platform has blocked a connection.
    Events include information about source and destination IP addresses and ports.

    auditpol /set /subcategory:"Filtering Platform Connection" /success:enable /failure:enable

    :param print_kwargs: Optional keyword arguments for the print function.
    """

    audit_policy_command = [
        "auditpol", "/set", '/subcategory:"Filtering Platform Connection"', "/success:enable", "/failure:enable"
    ]
    try:
        subprocess.run(audit_policy_command, check=True)
        print_api("Successfully enabled 'Audit Filtering Platform Connection'.", color='green', **(print_kwargs or {}))
    except subprocess.CalledProcessError as e:
        print_api(f"Failed to enable 'Audit Filtering Platform Connection': {e}", error_type=True, color='red', **(print_kwargs or {}))
        raise e
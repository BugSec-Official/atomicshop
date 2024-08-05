import subprocess
import sys

from ..print_api import print_api
from .. import permissions
from ..import get_process_list
from .psutilw import processes


ERROR_CODES = {
    '1603': 'The App is already installed or Insufficient permissions',
    '1619': 'This installation package could not be opened. Verify that the package exists and that you can '
            'install it manually, also check the installation command line switches'
}


class MsiInstallationError(Exception):
    pass


def get_current_msiexec_processes(msi_file_path: str = None) -> dict:
    """
    Get the current msiexec processes.
    :param msi_file_path: string, OPTIONAL path to the MSI file to check in the command line.
    :return: list of dicts, each key represents a pid and its values are process name and cmdline.
    """

    current_processes: dict = (
        get_process_list.GetProcessList(get_method='pywin32', connect_on_init=True).get_processes())

    current_msiexec_dict: dict = {}
    for pid, process_info in current_processes.items():
        if 'msiexec.exe' in process_info['name']:
            if msi_file_path:
                if msi_file_path in process_info['cmdline']:
                    current_msiexec_dict[pid] = process_info
            else:
                current_msiexec_dict[pid] = process_info

    return current_msiexec_dict


def wait_for_msiexec_processes_to_finish(msi_file_path: str):
    """
    Wait for the msiexec processes to finish.
    :param msi_file_path: string, path to the MSI file.
    :return:
    """

    current_msiexec: dict = get_current_msiexec_processes(msi_file_path)
    current_pid = list(current_msiexec.keys())[0]

    result_code = processes.wait_for_process(current_pid)
    if result_code != 0:
        raise Exception(f"MSI Installation failed. Return code: {result_code}")


def install_msi(
        msi_path,
        silent_no_gui: bool = False,
        silent_progress_bar: bool = False,
        no_restart: bool = False,
        terminate_required_processes: bool = False,
        additional_args: str = None,
        create_log_near_msi: bool = False,
        log_file_path: str = None,
        scan_log_for_errors: bool = False,
        # as_admin=True,
        print_kwargs: dict = None):
    """
    Install an MSI file silently.
    :param msi_path: str, path to the MSI file.
    :param silent_no_gui: bool, whether to run the installation silently, without showing GUI.
    :param silent_progress_bar: bool, whether to show a progress bar during silent installation.
    :param no_restart: bool, whether to restart the computer after installation.
    :param terminate_required_processes: bool, whether to terminate processes that are required by the installation.
    :param additional_args: str, additional arguments to pass to the msiexec command.
    :param create_log_near_msi: bool, whether to create a log file near the MSI file.
        If the msi file located in 'c:\\path\\to\\file.msi', the log file will be created in 'c:\\path\\to\\file.log'.
        The log options that will be used: /l*v c:\\path\\to\\file.log
    :param log_file_path: str, path to the log file. Even if 'create_log_near_msi' is False, you can specify a custom
        path for the log file, and it will be created.
        The log options that will be used: /l*v c:\\path\\to\\file.log
    :param scan_log_for_errors: bool, whether to scan the log file for errors in case of failure.
    # :param as_admin: bool, whether to run the installation as administrator.
    :param print_kwargs: dict, print_api kwargs.
    :return:
    """

    if not permissions.is_admin():
        raise PermissionError("This function requires administrator privileges.")

    if silent_progress_bar and silent_no_gui:
        raise ValueError("silent_progress_bar and silent_no_gui cannot be both True.")

    if create_log_near_msi and log_file_path:
        raise ValueError("create_log_near_msi and log_file_path cannot be both set.")

    if create_log_near_msi:
        log_file_path = msi_path.replace('.msi', '.log')

    if scan_log_for_errors and not log_file_path:
        raise ValueError("[scan_log_for_errors] is set, but [log_file_path] or [create_log_near_msi] is not set.")

    # Define the msiexec command
    command = f'msiexec /i "{msi_path}"'

    if silent_no_gui:
        command = f"{command} /qn"
    if silent_progress_bar:
        command = f"{command} /qb"
    if no_restart:
        command = f"{command} /norestart"

    if log_file_path:
        command = f"{command} /l*v {log_file_path}"

    if terminate_required_processes:
        command = f"{command} REBOOT=ReallySuppress"

    if additional_args:
        if additional_args.startswith(' '):
            additional_args = additional_args[1:]
        command = f"{command} {additional_args}"

    # if as_admin:
    #     command = permissions.get_command_to_run_as_admin_windows(command)

    # Run the command
    result = subprocess.run(command, capture_output=True, text=True)

    # Check the result
    if result.returncode == 0:
        print_api("MSI Installation completed.", color="green", **(print_kwargs or {}))
    else:
        message = (f"Installation failed. Return code: {result.returncode}\n{ERROR_CODES.get(str(result.returncode), '')}\n"
                   f"MSI path: {msi_path}\nCommand: {command}\nOutput: {result.stdout}\nError: {result.stderr}")

        if scan_log_for_errors:
            with open(log_file_path, 'r', encoding='utf-16 le') as f:
                log_content = f.read()
            if 'error' in log_content.lower():
                # Get the error text of the lines that contain 'error'.
                error_lines = [line for line in log_content.split('\n') if 'error' in line.lower()]
                for line in error_lines:
                    message += f"\n{line}"

        print_api(message, color="red", **(print_kwargs or {}))
        raise MsiInstallationError("MSI Installation Failed.")

import subprocess

from ..print_api import print_api
from .. import permissions


ERROR_CODES = {
    '1603': 'The App is already installed or Insufficient permissions',
    '1619': 'This installation package could not be opened. Verify that the package exists and that you can '
            'install it manually, also check the installation command line switches'
}


def install_msi(
        msi_path,
        silent_no_gui=True,
        silent_progress_bar=False,
        no_restart=True,
        as_admin=False,
        exit_on_error=False,
        print_kwargs=None):
    """
    Install an MSI file silently.
    :param msi_path: str, path to the MSI file.
    :param silent_no_gui: bool, whether to run the installation silently, without showing GUI.
    :param silent_progress_bar: bool, whether to show a progress bar during silent installation.
    :param no_restart: bool, whether to restart the computer after installation.
    :param as_admin: bool, whether to run the installation as administrator.
    :param exit_on_error: bool, whether to exit the script if the installation fails.
    :param print_kwargs: dict, print_api kwargs.
    :return:
    """

    if silent_progress_bar and silent_no_gui:
        raise ValueError("silent_progress_bar and silent_no_gui cannot be both True.")

    # Define the msiexec command
    command = f'msiexec /i "{msi_path}"'

    if silent_no_gui:
        command = f"{command} /qn"
    if silent_progress_bar:
        command = f"{command} /qb"
    if no_restart:
        command = f"{command} /norestart"

    if as_admin:
        command = permissions.get_command_to_run_as_admin_windows(command)

    # Run the command
    result = subprocess.run(command, capture_output=True, shell=True, text=True)

    # Check the result
    if result.returncode == 0:
        print_api("MSI Installation completed.", color="green", **(print_kwargs or {}))
    else:
        message = f"Installation failed. Return code: {result.returncode}\n{ERROR_CODES.get(str(result.returncode), '')}"
        print_api(message, color="red", **(print_kwargs or {}))
        if exit_on_error:
            exit()

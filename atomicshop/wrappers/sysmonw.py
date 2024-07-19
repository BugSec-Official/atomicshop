import os
import subprocess

from .. import filesystem, web, process


# Define paths and configuration
DEFAULT_INSTALLATION_PATH: str = 'C:\\Sysmon'
SYSMON_FILE_NAME: str = 'Sysmon.exe'
SYSINTERNALS_SYSMON_URL: str = 'https://download.sysinternals.com/files/Sysmon.zip'
SYSMON_CONFIG_FILE_NAME: str = 'sysmonconfig.xml'
SYSMON_CONFIG_FILE_PATH: str = os.path.join(DEFAULT_INSTALLATION_PATH, SYSMON_CONFIG_FILE_NAME)


class ConfigFileNotFoundError(Exception):
    pass


class SymonExecutableNotFoundError(Exception):
    pass


class SysmonAlreadyRunningError(Exception):
    pass


def download_sysmon(installation_path: str = None):
    """
    Install Sysmon on the system.

    :param installation_path: string, full path where to put the Sysmon executable.
    """

    if not installation_path:
        installation_path = DEFAULT_INSTALLATION_PATH

    # Check if the file exists
    if not os.path.exists(installation_path):
        filesystem.create_directory(installation_path)

    web.download_and_extract_file(SYSINTERNALS_SYSMON_URL, installation_path)


def is_sysmon_running():
    """
    Check if Sysmon is running.

    :return: boolean, True if Sysmon is running, False otherwise.
    """

    process_list: list = process.match_pattern_against_running_processes_cmdlines(
        pattern=SYSMON_FILE_NAME, first=True, process_name_case_insensitive=True)

    if process_list:
        return True
    else:
        return False


def start_as_service(
        installation_path: str = None,
        config_file_path: str = None,
        use_config_in_same_directory: bool = False,
        download_sysmon_if_not_found: bool = False,
        skip_if_running: bool = False
):
    """
    Start Sysmon as a service. Besides starting, it installs itself as a service, meaning that on the next boot,
    it will start automatically.

    :param installation_path: string, full path where to put the Sysmon executable.
    :param config_file_path: string, full path to the configuration file.
    :param use_config_in_same_directory: boolean, if True, the function will use the configuration file in the same
        directory as the Sysmon executable.
    :param download_sysmon_if_not_found: boolean, if True, the function will download Sysmon if it is not
        found in the 'installation_path'.
    :param skip_if_running: boolean,
        True, the function will not start Sysmon if it is already running.
        False, the function will raise 'SysmonAlreadyRunningError' exception if it is already running.
    """

    # Check if sysmon already running.
    if is_sysmon_running():
        if skip_if_running:
            return
        else:
            raise SysmonAlreadyRunningError("Sysmon is already running.")

    if config_file_path and use_config_in_same_directory:
        raise ValueError("You cannot use both 'config_file_path' and 'use_config_in_same_directory'.")

    if use_config_in_same_directory:
        config_file_path = SYSMON_CONFIG_FILE_PATH

    # Check if the file exists
    if not os.path.exists(config_file_path):
        raise ConfigFileNotFoundError(f"Configuration file '{config_file_path}' not found.")

    if not installation_path:
        installation_path = DEFAULT_INSTALLATION_PATH

    sysmon_file_path: str = os.path.join(installation_path, SYSMON_FILE_NAME)

    # Check if the file exists
    if not os.path.exists(sysmon_file_path):
        if download_sysmon_if_not_found:
            download_sysmon(installation_path)
        else:
            raise SymonExecutableNotFoundError(f"Sysmon executable '{sysmon_file_path}' not found.")

    # Start Sysmon as a service.
    subprocess.run([sysmon_file_path, '-accepteula', '-i', config_file_path])


def stop_service(installation_path: str = None):
    """
    Stop Sysmon service.

    :param installation_path: string, full path where to put the Sysmon executable.
    """

    if not installation_path:
        installation_path = DEFAULT_INSTALLATION_PATH

    sysmon_file_path: str = os.path.join(installation_path, SYSMON_FILE_NAME)

    # Check if the file exists
    if not os.path.exists(sysmon_file_path):
        raise SymonExecutableNotFoundError(f"Sysmon executable '{sysmon_file_path}' not found.")

    # Stop Sysmon service.
    subprocess.run([sysmon_file_path, '-u'])


def change_config_on_the_fly(config_file_path: str, installation_path: str = None):
    """
    Change the Sysmon configuration on the fly.

    :param config_file_path: string, full path to the configuration file.
    :param installation_path: string, full path where to put the Sysmon executable.
    """

    if not installation_path:
        installation_path = DEFAULT_INSTALLATION_PATH

    sysmon_file_path: str = os.path.join(installation_path, SYSMON_FILE_NAME)

    # Check if the file exists
    if not os.path.exists(sysmon_file_path):
        raise SymonExecutableNotFoundError(f"Sysmon executable '{sysmon_file_path}' not found.")

    # Change the configuration on the fly.
    subprocess.run([sysmon_file_path, '-c', config_file_path])

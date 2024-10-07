from typing import Union, Literal
from pathlib import Path

from .... import process, print_api
from .. import config_install


PLUGIN_LIST: list = [
    'qemu_exec',
    'binwalk',
    'users_and_passwords',
    'kernel_config',
    'cve_lookup',
    'crypto_hints',
    'input_vectors',
    'cwe_checker',
    'linter',
    'ip_and_uri_finder',
    'device_tree',
    'file_system_metadata',
    'ipc',
    'software_components',
    'architecture_detection',
    'known_vulnerabilities'
]


INSTALLING_STRINGS: list = ['Installing', 'plugin']
FINISHED_INSTALLING_STRINGS: list = ['Finished installing', 'plugin']
LOG_FINISHED_STRING: str = 'installation complete'


def install_after_restart(
        installation_directory: str,
        install_type: Union[
            None,
            Literal['backend', 'frontend', 'db']] = None,
        log_level: Union[
            None,
            Literal['DEBUG', 'INFO', 'WARNING', 'ERROR']] = None,
        log_file: Union[
            None,
            str] = None,
        analyze_log: bool = False
) -> int:
    """
    This function will continue the installation the FACT_core after the restart of the computer.

    :param installation_directory: string, the directory where the FACT_core was downloaded to during pre install.
    :param install_type: this parameter will be used for the 'install.py' script of the FACT_core.
        From this help: https://github.com/fkie-cad/FACT_core/blob/master/INSTALL.md

        None: Non-distributed setup, Install the FACT_core backend, frontend and database.
        --backend: Distributed setup, Install the FACT_core backend.
        --frontend: Distributed setup, Install the FACT_core frontend.
        --db: Distributed setup, Install the FACT_core database.
    :param log_level: string, the log level to use for the installation.
        The same as using the '--log-level' parameter in the 'install.py' script.
        The default is 'INFO' in the 'install.py' script.
    :param log_file: string, the log file to use for the installation.
        The same as using the '--log-file' parameter in the 'install.py' script.
    :param analyze_log: bool, if True, the log file will be analyzed for plugin installation errors.
    :return: int, 0 if the installation was successful, otherwise 1.
    """

    install_command: str = 'python3 "' + str(Path(installation_directory, config_install.INSTALL_FILE_PATH)) + '"'

    if install_type:
        install_command = install_command + ' --' + install_type

    if log_level:
        install_command = install_command + ' --log_level ' + log_level

    if log_file:
        install_command = install_command + ' --log_file "' + log_file + '"'

    # Install the FACT_core repo.
    process.execute_with_live_output(cmd=install_command, verbose=True)

    # Analyze the log file for errors.
    if analyze_log and (install_type == 'backend' or install_type is None):
        if not log_file:
            log_file = str(Path.cwd() / config_install.INSTALL_LOG_FILE_NAME)

        return analyze_log_file(log_file=log_file)

    # Remove the FACT_core installation log.
    # working_directory_path: str = filesystem.get_working_directory()
    # filesystem.remove_file(str(Path(working_directory_path, config_install.INSTALL_LOG_FILE_NAME)))

    return 0


def analyze_log_file(log_file: str):
    """
    This function will analyze the log file for plugin installation errors.
    :param log_file:
    :return:
    """

    with open(log_file, 'r') as file:
        log_content: str = file.read()

    for plugin in PLUGIN_LIST:
        if f'{FINISHED_INSTALLING_STRINGS[0]} {plugin} {FINISHED_INSTALLING_STRINGS[1]}' not in log_content:
            message = (f'Error: [{plugin}] installation failed.\n'
                       f'Check the log file: {log_file}\n'
                       f'Exiting...')
            print_api.print_api(message, color='red')
            return 1

    if LOG_FINISHED_STRING not in log_content:
        message = (f'Error: Installation failed.\n'
                   f'Check the log file: {log_file}\n'
                   f'Exiting...')
        print_api.print_api(message, color='red')
        return 1

    return 0

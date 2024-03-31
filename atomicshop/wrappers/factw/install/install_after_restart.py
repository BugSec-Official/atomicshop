from typing import Union, Literal
from pathlib import Path

from .... import process, filesystem
from .. import config_install


def install_after_restart(
        installation_directory: str,
        install_type: Union[None, Literal['backend', 'frontend', 'db']] = None
):
    """
    This function will continue the installation the FACT_core after the restart of the computer.

    :param installation_directory: string, the directory where the FACT_core was downloaded to during pre install.
    :param install_type: this parameter will be used for the 'install.py' script of the FACT_core.
        From this help: https://github.com/fkie-cad/FACT_core/blob/master/INSTALL.md

        None: Non-distributed setup, Install the FACT_core backend, frontend and database.
        --backend: Distributed setup, Install the FACT_core backend.
        --frontend: Distributed setup, Install the FACT_core frontend.
        --db: Distributed setup, Install the FACT_core database.
    :return:
    """

    install_command: str = 'python3 "' + str(Path(installation_directory, config_install.INSTALL_FILE_PATH)) + '"'

    if install_type:
        install_command = install_command + ' --' + install_type

    # Install the FACT_core repo.
    process.execute_with_live_output(cmd=install_command, verbose=True)
    # Remove the FACT_core installation log.
    working_directory_path: str = filesystem.get_working_directory()
    filesystem.remove_file(str(Path(working_directory_path, config_install.INSTALL_LOG_FILE_NAME)))

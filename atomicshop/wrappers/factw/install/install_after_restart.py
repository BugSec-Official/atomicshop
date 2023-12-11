from typing import Union, Literal
from pathlib import Path
import subprocess

from .... import permissions
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
    if not permissions.is_admin():
        print("This script requires root privileges. Please enter your password for sudo access.")
        permissions.run_as_root(['-v'])

    install_command: str = 'python3 ' + str(Path(installation_directory, config_install.INSTALL_FILE_PATH))

    if install_type:
        install_command = install_command + ' --' + install_type

    # Install the FACT_core repo.
    subprocess.run(install_command)
    # Remove the FACT_core installation log.
    # filesystem.remove_file(config_static_install.FACT_CORE_INSTALL_LOG_FILE_PATH)

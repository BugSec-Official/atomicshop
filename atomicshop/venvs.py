import sys
import os
from typing import Union


def is_running_venv() -> Union[str, None]:
    """
    Check if the script is running in a virtual environment.

    :return: string of the virtual environment path if it is running in a virtual environment, None otherwise.
    """
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        return sys.prefix
    else:
        return None


def add_venv_to_path():
    """
    Add the virtual environment to the PATH environment variable.
    """

    venv_environment = is_running_venv()
    if venv_environment:
        # We're in a virtual environment, so modify the PATH
        venv_bin = os.path.join(venv_environment, 'bin')
        # Prepend the virtual environment's bin directory to the existing PATH
        os.environ['PATH'] = f"{venv_bin}:{os.environ['PATH']}"

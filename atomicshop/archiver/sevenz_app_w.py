import os
import subprocess
from pathlib import Path

from ..print_api import print_api
from .. import process


def is_path_contains_7z_executable(sevenz_path: str) -> bool:
    """
    Checks if the path contains 7z executable.
    :param sevenz_path: string, The path to the 7z executable.
    :return: bool, True if the path contains 7z executable, False otherwise.
    """
    executable_path_parts: tuple = Path(sevenz_path).parts

    if '7z' not in executable_path_parts[-1]:
        return False
    else:
        return True


def is_executable_a_7z(sevenz_path: str) -> bool:
    """
    Checks if the 7z executable is installed.
    :param sevenz_path: string, The path to the 7z executable.
    :return: bool, True if the 7z executable is installed, False otherwise.
    """

    # Check if the process itself is installed.
    if process.is_command_exists(sevenz_path):
        # Check that this is the 7z executable.
        try:
            # Run '7z' command and capture output
            result = subprocess.run([sevenz_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Check if the output contains identifying information
            if b"7-Zip" in result.stdout or b"7-Zip" in result.stderr:
                return True
        except Exception:
            return False

        return False


def extract_file(
        file_path: str,
        extract_to: str,
        sevenz_path: str = None,
        force_overwrite: bool = False,
        print_kwargs: dict = None
):
    """
    Extracts a file to a directory using 7z executable.
    :param file_path: string, The path to the file to extract.
    :param extract_to: string, The directory to extract the file to.
    :param sevenz_path: string, The path to the 7z executable.
        If None, the default path is used, assuming you added 7z to the PATH environment variable.
    :param force_overwrite: bool, If True, the files will be overwritten if they already exist in the output folder.
    :param print_kwargs: dict, The keyword arguments to pass to the print function.
    :return:
    """

    # Check if the path contains 7z executable.
    if not is_path_contains_7z_executable(sevenz_path):
        raise ValueError("The path to 7z does not contain 7z executable")

    if not sevenz_path:
        sevenz_path = '7z'

    # Check if the 7z executable is installed.
    if not is_executable_a_7z(sevenz_path):
        raise RuntimeError("'7z executable' is not a 7z")

    if not os.path.exists(extract_to):
        os.makedirs(extract_to)

    command = [f'{sevenz_path}', 'x', file_path, f'-o{extract_to}']
    if force_overwrite:
        command.append('-y')

    try:
        subprocess.run(command, check=True)
        print_api(f"Extracted {file_path} to {extract_to}", **(print_kwargs or {}))
    except subprocess.CalledProcessError as e:
        print_api(f"An error occurred: {e}", **(print_kwargs or {}))

import os
from pathlib import Path

from ...wrappers.pywin32w import winshell


STARTUP_FOLDER = os.path.join(os.environ['APPDATA'], 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')


def add_to_startup_folder_with_shortcut(exe_file_path: str, shortcut_name: str) -> str:
    """
    This function will create a shortcut in the startup folder to your executable.

    :param exe_file_path: The path to your executable file.
    :param shortcut_name: The name of the shortcut file to create in the startup folder.
        No need to add the ".lnk" extension.
    :return: The path to the shortcut file created.
    """

    # Get the startup folder path and create if non-existent.
    Path(STARTUP_FOLDER).mkdir(parents=True, exist_ok=True)

    shortcut_file_path = str(Path(STARTUP_FOLDER, f'{shortcut_name}.lnk'))

    # Create a shortcut to the executable file.
    winshell.create_shortcut(exe_file_path, shortcut_file_path)

    return shortcut_file_path


def is_in_startup_folder(shortcut_name: str):
    """
    This function will check if the shortcut is in the startup folder.

    :param shortcut_name: The name of the shortcut file to check in the startup folder.
        No need to add the ".LNK" extension.
    :return: True if the shortcut is in the startup folder, False otherwise.
    """
    return Path(STARTUP_FOLDER, f'{shortcut_name}.lnk').exists()


def remove_from_startup_folder(shortcut_name: str):
    """
    This function will remove the shortcut from the startup folder.

    :param shortcut_name: The name of the shortcut file to remove from the startup folder.
        No need to add the ".LNK" extension.
    """
    shortcut_file_path = Path(STARTUP_FOLDER, f'{shortcut_name}.lnk')
    if shortcut_file_path.exists():
        shortcut_file_path.unlink()
        return True
    return False

from pathlib import Path

from win32com.client import Dispatch


def create_shortcut(file_path_to_link: str, shortcut_file_path: str):
    """
    Create a shortcut in the startup folder to the specified file.

    :param file_path_to_link: The path to the file you want to create a shortcut to.
    :param shortcut_file_path: The name of the shortcut file. Should be with the ".lnk" extension.
    """

    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(shortcut_file_path)
    shortcut.Targetpath = file_path_to_link
    shortcut.WorkingDirectory = str(Path(file_path_to_link).parent)
    shortcut.Description = f"Shortcut for {Path(file_path_to_link).name}"
    shortcut.save()

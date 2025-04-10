import os
import pathlib
from pathlib import Path, PurePath, PureWindowsPath, PurePosixPath
import glob
import shutil
import stat
import errno
from contextlib import contextmanager
from typing import Literal, Union
import tempfile

# noinspection PyPackageRequirements
import psutil

from .basics import strings, list_of_dicts, list_of_classes
from .file_io import file_io
from . import hashing, datetimes, print_api


WINDOWS_DIRECTORY_SPECIAL_CHARACTERS = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
FILE_NAME_REPLACEMENT_DICT: dict = {
    '$': '_',
    ' ': '_',
    '(': '_',
    ')': '_',
    '[': '_',
    ']': '_',
    '{': '_',
    '}': '_',
    "'": "_",
    '"': '_',
    '`': '_',
    ';': '_',
    '&': '_',
    '|': '_',
    '*': '_',
    '?': '_',
    '~': '_',
    '#': '_',
    '=': '_',
    '+': '_',
    '%': '_',
    ',': '_',
    '^': '_',
    ':': '_',
    '@': '_',
    '!': '_',
    '°': '_',
    '§': '_',
    '²': '_',
    '³': '_',
    'µ': '_',
    '€': '_',
    '£': '_',
    '¥': '_',
    '¢': '_',
    '©': '_',
    '®': '_',
    '™': '_',
    '×': '_',
    '÷': '_',
    '¶': '_',
    '·': '_',
    '¹': '_'
}


# class TimeCouldNotBeFoundInFileNameError(Exception):
#     pass


def get_home_directory(return_sudo_user: bool = False) -> str:
    """
    Returns the home directory of the current user or the user who invoked sudo.

    :param return_sudo_user: bool, if 'False', then the function will return the home directory of the user who invoked
        sudo (if the script was invoked with sudo).
        If 'True', then the function will return the home directory of the current user, doesn't matter if the script
        was invoked with sudo or not, if so home directory of the sudo user will be returned.
    """

    def return_home_directory_of_current_user():
        """
        Returns the home directory of the current user.
        """
        return os.path.expanduser('~')

    # Check if the script is run using sudo
    if 'SUDO_USER' in os.environ:
        # If 'return_sudo_user' is set to 'True', return the home directory of the sudo user.
        if return_sudo_user:
            return_home_directory_of_current_user()
        else:
            # Get the home directory of the user who invoked sudo
            return os.path.expanduser(f"~{os.environ['SUDO_USER']}")

    # Get the current user's home directory
    return return_home_directory_of_current_user()


def create_empty_file(file_path: str) -> None:
    """
    The function creates an empty file.

    :param file_path: string, full path to file.
    :return: None.
    """

    # Create empty file.
    Path(file_path).touch()


def get_working_directory() -> str:
    """
    The function returns working directory of called script file.
    If the function is placed in other file and is called from the main script, it will return
    the main script directory and not the file that the function is in.

    :return: string.
    """
    return str(Path.cwd())


def get_temp_directory() -> str:
    """
    The function returns temporary directory of the system.

    :return: string.
    """

    # Get the temporary directory in 8.3 format
    short_temp_dir = tempfile.gettempdir()

    # Convert to the long path name
    long_temp_dir = str(Path(short_temp_dir).resolve())

    return long_temp_dir


def get_file_directory(file_path: str) -> str:
    """
    The function will return directory of the file.

    :param file_path: string, full file path.
    :return: string.
    """
    return str(Path(file_path).parent)


def add_object_to_path(path: str, object_string: str) -> str:
    """
    The function will add directory to the path.
    Example: 'C:/Users/user1' + 'Downloads' = 'C:/Users/user1/Downloads'

    :param path: string, path.
    :param object_string: string, directory or file.

    :return: string, of the new path.
    """

    return os.path.join(path, object_string)


def get_file_name_with_extension(file_path: str) -> str:
    """
    The function will return file name with extension of the file.

    :param file_path: string, full file path.
    :return: string.
    """
    return str(Path(file_path).name)


def get_file_name_without_extension(file_path: str) -> str:
    """
    The function will return file name without extension of the file.

    :param file_path: string, full file path.
    :return: string.
    """
    return str(Path(file_path).stem)


def get_list_of_directories_in_file_path(
        file_path: str, get_last_part: bool = True, convert_drive_to_string: bool = False) -> list:
    """
    The function will return list of directories in the file path.

    :param file_path: string, full file path.
    :param get_last_part: boolean, if True, the last part of the path will be included in the list.
        In most cases only user can know if it is a file name or not, so you decide if you want to remove it or not.
    :param convert_drive_to_string: boolean, if True, the drive letter will be converted to a single character string.
        Only if the path is a Windows path and contains a drive letter.
        Example: 'C:' will be converted to 'C'. 'C:\' will be converted to 'C'. '\\C:\\' will be converted to 'C'.
    :return: list.
    """

    # If we're on Windows, convert the path to a Windows path.
    if os.name == 'nt':
        directory_list = list(PureWindowsPath(file_path).parts)
    else:
        directory_list = list(PurePath(file_path).parts)

    # If 'convert_drive_to_string' was set to 'True' and the path is a Windows path and the first directory contains
    # a drive letter, convert it to a single character string.
    if convert_drive_to_string and strings.contains_letter(directory_list[0]) and os.name == 'nt':
        directory_list[0] = directory_list[0].replace(':', '').replace('\\', '')

    # If 'get_last_part' is set to 'False', remove the last part of the path.
    if not get_last_part:
        del directory_list[-1]

    return directory_list


def check_absolute_path(filesystem_path) -> bool:
    """
    The function checks if the path provided is a full path (absolute) or relative.

    :param filesystem_path: string, filesystem path to check. Can be file or directory.
    :return: bool.
    """
    return Path(filesystem_path).is_absolute()


def check_absolute_path___add_full(filesystem_path: str, full_path_to_add: str) -> str:
    """
    The function checks if 'filesystem_path' is a full path (absolute path) or relative. If it is a relative path,
        then, 'full_path_to_add' is added to beginning of 'filesystem_path' including a separator.

    :param filesystem_path: string, of filesystem path to check, can be directory or file path.
    :param full_path_to_add: string, full path to be added in case 'filesystem_path' is not absolute.
    :return: string.
    """

    if not check_absolute_path(filesystem_path):
        return f'{full_path_to_add}{os.sep}{remove_last_separator(filesystem_path)}'
    else:
        return filesystem_path


def is_file_exists(file_path: str) -> bool:
    """
    Function to check if the path is a file.

    :param file_path: String path to file to check.
    :return: Return boolean answer if file exists or not.
    """

    # Check if "file_path" variable is a full file path.
    if os.path.isfile(file_path):
        return True
    else:
        return False


def is_directory_exists(directory_path: str) -> bool:
    """
    Function to check if a path is a directory.

    :param directory_path: String path to file to check.
    :return: Return boolean answer if file exists or not.
    """

    # Check if "directory_path" variable is a full directory path
    if os.path.isdir(directory_path):
        return True
    else:
        return False


def remove_file(file_path: str, **kwargs) -> bool:
    """
    Remove file if it exists, since the file is being appended every time it runs.

    :param file_path: string to full file path.
    :return: return 'True' if file removal succeeded, and 'False' if not.
    """

    try:
        os.remove(file_path)
        print_api.print_api(f'File Removed: {file_path}')
        return True
    # Since the file doesn't exist, we actually don't care, since we want to remove it anyway.
    except FileNotFoundError:
        message = f'File Removal Failed, File non-existent: {file_path}'
        print_api.print_api(message, error_type=True, logger_method='critical', **kwargs)
        return False


def remove_directory(directory_path: str, force_readonly: bool = False, print_kwargs: dict = None) -> bool:
    """
    Remove directory if it exists.

    :param directory_path: string to full directory path.
    :param force_readonly: boolean, if 'True', then the function will try to remove the read-only attribute from the
        directory and its contents.
    :param print_kwargs: dict, kwargs for print_api.

    :return: return 'True' if directory removal succeeded, and 'False' if not.
    """

    def remove_readonly(func, path, exc_info):
        # Catch the exception
        excvalue = exc_info[1]
        if excvalue.errno == errno.EACCES:
            # Change the file or directory to be writable, readable, and executable: 0o777
            os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)  # 0o777
            # Retry the removal
            func(path)
        else:
            # Re-raise the exception if it's not a permission error
            raise

    if print_kwargs is None:
        print_kwargs = dict()

    try:
        if force_readonly:
            shutil.rmtree(directory_path, onerror=remove_readonly)
        else:
            shutil.rmtree(directory_path)
        print_api.print_api(f'Directory Removed: {directory_path}', **print_kwargs)
        return True
    # Since the directory doesn't exist, we actually don't care, since we want to remove it anyway.
    except FileNotFoundError:
        message = f'Directory Removal Failed, Directory non-existent: {directory_path}'
        print_api.print_api(message, error_type=True, logger_method='critical', **print_kwargs)
        return False


def clear_directory(directory: str) -> tuple[list[str], list[str]]:
    """
    The function will clear the directory of all files and subdirectories.
    :param directory:
    :return: tuple of lists of removed file paths and removed directory paths.
    """

    file_paths: list = []
    directory_paths: list = []
    # Iterate through all files and subdirectories in the directory
    for item in os.listdir(directory):
        item_path = os.path.join(directory, item)
        # If it's a file, remove it
        if os.path.isfile(item_path) or os.path.islink(item_path):  # Handle symbolic links too
            os.remove(item_path)
            file_paths.append(item_path)
        # If it's a directory, remove it and its contents
        elif os.path.isdir(item_path):
            shutil.rmtree(item_path)
            directory_paths.append(item_path)

    return file_paths, directory_paths


def remove_empty_directories(directory_path: str) -> list[str]:
    """
    Recursively removes empty directories in the given path, including the given path if it is empty.

    :param directory_path: The starting directory path to check and remove empty directories.
    """
    if not os.path.isdir(directory_path):
        # print(f"Path '{directory_path}' is not a directory or does not exist.")
        return []

    removed_directories: list = []
    # Iterate through the directory contents
    for root, dirs, files in os.walk(directory_path, topdown=False):
        for directory in dirs:
            dir_path = os.path.join(root, directory)
            # Check if the directory is empty
            if not os.listdir(dir_path):
                os.rmdir(dir_path)
                removed_directories.append(dir_path)
                # print(f"Removed empty directory: {dir_path}")

    # Finally, check if the top-level directory is empty
    if not os.listdir(directory_path):
        os.rmdir(directory_path)
        removed_directories.append(directory_path)
        # print(f"Removed top-level empty directory: {path}")

    return removed_directories


def create_directory(directory_fullpath: str):
    # Create directory if non-existent.
    # The library is used to create folder if it doesn't exist and won't raise exception if it does
    # 'parents=True' will create also the parent folders of the last folder, not used in our case
    # 'exist_ok=True' if the folder exists, then it is ok.
    pathlib.Path(directory_fullpath).mkdir(parents=True, exist_ok=True)


def rename_file(file_path: str, new_file_name: str) -> None:
    """
    The function renames file from source to target.

    :param file_path: string, full path to file that will be renamed.
    :param new_file_name: string, new name of the file. No path should be included.

    :return: None
    """

    renamed_file_path = str(Path(file_path).parent) + os.sep + new_file_name

    # Rename file.
    os.rename(file_path, renamed_file_path)


def rename_file_with_special_characters(
        file_path: str,
        rename_dictionary: dict = None,
) -> str:
    """
    The function will rename the file to replace special characters from the file name with '_'.
    If the file already exists, then the function will add a number to the end of the file name.

    :param file_path: string, full path to file.
    :param rename_dictionary: dictionary, with special characters to replace.
        If not specified, the default dictionary will be used: FILE_NAME_REPLACEMENT_DICT.
        Example:
            rename_dictionary = {
                '$': '_',
                ' ': '_'
            }
    :return: string, full path to file with special characters renamed.
    """

    if rename_dictionary is None:
        rename_dictionary = FILE_NAME_REPLACEMENT_DICT

    # Get the file name without extension
    file_stem: str = str(Path(file_path).stem)
    file_extension: str = str(Path(file_path).suffix)

    # Remove special characters from the file name
    new_file_stem = strings.replace_strings_with_values_from_dict(
        string_to_replace=file_stem, dictionary=rename_dictionary)

    # Rename the file
    renamed_file_path = str(Path(file_path).parent) + os.sep + new_file_stem + file_extension

    counter: int = 1
    if os.path.isfile(renamed_file_path):
        while True:
            new_file_stem = f'{new_file_stem}_{counter}'
            renamed_file_path = str(Path(file_path).parent) + os.sep + new_file_stem + file_extension
            if not os.path.isfile(renamed_file_path):
                break
            counter += 1

    os.rename(file_path, renamed_file_path)

    return renamed_file_path


def rename_files_and_directories_with_special_characters(
        base_path: str,
        rename_dictionary: dict = None
) -> None:
    """
    Recursively renames all files and directories in the given directory to rename special characters.

    :param base_path: str, the base directory to start processing.
    :param rename_dictionary: dictionary, with special characters to replace.
        If not specified, the default dictionary will be used: FILE_NAME_REPLACEMENT_DICT.
        Example:
            rename_dictionary = {
                '$': '_',
                ' ': '_'
            }
    """

    def sanitize_name(name: str) -> str:
        nonlocal rename_dictionary
        """
        Helper function to replace special characters in a string using a dictionary.
        """
        for key, value in rename_dictionary.items():
            name = name.replace(key, value)
        return name

    if rename_dictionary is None:
        rename_dictionary = FILE_NAME_REPLACEMENT_DICT

    # Walk through the directory tree in reverse to ensure we rename files before directories
    for root, dirs, files in os.walk(base_path, topdown=False):
        # Rename files in the current directory
        for file_name in files:
            old_path = Path(root) / file_name
            sanitized_name = sanitize_name(file_name)
            new_path = Path(root) / sanitized_name

            if sanitized_name != file_name:  # Rename only if the name changed
                # print(f"Renaming file: {old_path} -> {new_path}")
                os.rename(old_path, new_path)

        # Rename directories in the current directory
        for dir_name in dirs:
            old_path = Path(root) / dir_name
            sanitized_name = sanitize_name(dir_name)
            new_path = Path(root) / sanitized_name

            if sanitized_name != dir_name:  # Rename only if the name changed
                # print(f"Renaming directory: {old_path} -> {new_path}")
                os.rename(old_path, new_path)


@contextmanager
def temporary_rename(file_path: str, temp_file_path) -> None:
    # noinspection GrazieInspection
    """
        The function will rename the file to temporary name and then rename it back to original name.

        :param file_path: string, full path to file.
        :param temp_file_path: string, temporary name to rename the file to.
        :return: None.

        Usage:
            original_file = 'example.txt'
            temporary_file = 'temp_example.txt'

            with temporary_rename(original_file, temporary_file):
                # Inside this block, the file exists as 'temp_example.txt'
                print(f"File is temporarily renamed to {temporary_file}")
                # Perform operations with the temporarily named file here

            # Outside the block, it's back to 'example.txt'
            print(f"File is renamed back to {original_file}")
        """

    original_name = file_path
    try:
        # Rename the file to the temporary name
        os.rename(original_name, temp_file_path)
        yield
    finally:
        # Rename the file back to its original name
        os.rename(temp_file_path, original_name)


@contextmanager
def temporary_copy(file_path: str, temp_file_path) -> None:
    """
    The function will copy the file temporarily and then delete it.
    :param file_path: string, full path to file.
    :param temp_file_path: string, temporary path to copy the file to.
    :return:
    """

    original_name = file_path
    try:
        # Copy the file to the temporary path
        shutil.copy2(original_name, temp_file_path)
        yield
    finally:
        # Delete the file
        os.remove(temp_file_path)


@contextmanager
def temporary_change_working_directory(new_working_directory: str) -> None:
    """
    The function will change the working directory temporarily and then change it back.
    :param new_working_directory: string, new working directory.
    :return:
    """

    original_working_directory = get_working_directory()
    try:
        # Change the working directory to the temporary path
        os.chdir(new_working_directory)
        yield
    finally:
        # Change the working directory back to the original working directory
        os.chdir(original_working_directory)


def move_file(source_file_path: str, target_directory: str, overwrite: bool = True) -> None:
    """
    The function moves file from source to target.

    :param source_file_path: string, full path to source file.
    :param target_directory: string, full path to target directory.
    :param overwrite: boolean, if 'False', then the function will not overwrite the file if it exists.

    Example:
        Before move:
        Source file = 'C:/Users/user1/Downloads/file-to-move.txt'
        Move to directory = 'C:/Users/user1/Documents'

        Move:
        source_file_path = 'C:/Users/user1/Downloads/file-to-move.txt'
        target_directory = 'C:/Users/user1/Documents'
        move_file(source_file_path, target_file_path)

        After move:
        'C:/Users/user1/Downloads'
        'C:/Users/user1/Documents/file-to-move.txt'

    :return: None
    """

    target_file_path = target_directory + os.sep + Path(source_file_path).name

    # Check if 'no_overwrite' is set to 'True' and if the file exists.
    if not overwrite:
        if is_file_exists(target_file_path):
            raise FileExistsError(f'File already exists: {target_file_path}')

    # Move file.
    shutil.move(source_file_path, target_file_path)


def move_folder(source_directory: str, target_directory: str, overwrite: bool = True) -> None:
    """
    The function moves folder from source to target.

    :param source_directory: string, full path to source directory.
    :param target_directory: string, full path to target directory.
    :param overwrite: boolean, if 'False', then the function will not overwrite the directory if it exists.

    :return: None

    ------------------------------

    Example:
        Before move:
        Source folder = 'C:/Users/user1/Downloads/folder-to-move'
        Move to directory = 'C:/Users/user1/Documents'

        Move:
        source_directory = 'C:/Users/user1/Downloads/folder-to-move'
        target_directory = 'C:/Users/user1/Documents'
        move_folder(source_directory, target_directory)

        Result path of the 'folder-to-move' will be:
        'C:/Users/user1/Documents/folder-to-move'

    """

    # Check if 'overwrite' is set to 'True' and if the directory exists.
    if not overwrite:
        if is_directory_exists(target_directory):
            raise FileExistsError(f'Directory already exists: {target_directory}')

    # Move directory.
    shutil.move(source_directory, target_directory)


def move_top_level_files_from_folder_to_folder(
        source_directory: str,
        target_directory: str,
        overwrite: bool = True
):
    """
    The function is non-recursive to move only top level files from source directory to target directory
    overwriting existing files.

    :param source_directory: string, full path to source directory.
    :param target_directory: string, full path to target directory.
    :param overwrite: boolean, if 'False', then the function will not overwrite the files if they exist.
    """

    # Iterate over each item in the source directory
    top_level_files: list[str] = get_paths_from_directory(
        directory_path=source_directory, get_file=True, recursive=False, simple_list=True)

    for source_item in top_level_files:
        # Move each item to the destination directory
        move_file(source_file_path=source_item, target_directory=target_directory, overwrite=overwrite)


def move_folder_contents_to_folder(
        source_directory: str,
        target_directory: str,
        overwrite: bool = True
):
    """
    The function moves all the contents of the source directory to the target directory.
    If target directory is inside the source directory, this folder will be skipped.

    :param source_directory: string, full path to source directory.
    :param target_directory: string, full path to target directory.
    :param overwrite: boolean, if 'True', then the function will overwrite the files if they exist.
    """

    # Make sure the destination directory exists, if not create it
    os.makedirs(target_directory, exist_ok=True)

    # Move contents of the source directory to the destination directory
    for item in os.listdir(source_directory):
        s = os.path.join(source_directory, item)
        d = os.path.join(target_directory, item)

        # if the target directory is inside the source directory, skip it
        if os.path.abspath(target_directory).startswith(os.path.abspath(s)):
            continue

        if os.path.isdir(s):
            if os.path.exists(d) and not overwrite:
                raise FileExistsError(f"Directory already exists: {d}. Skipping due to overwrite=False.")
            else:
                shutil.move(s, d)
        else:
            if os.path.exists(d) and not overwrite:
                raise FileExistsError(f"File {d} already exists. Skipping due to overwrite=False.")
            else:
                shutil.move(s, d)


def copy_file(
        source_file_path: str,
        target_file_path: str,
        no_overwrite: bool = False,
        preserve_metadata: bool = False
) -> None:
    """
    The function copies file from source to target.

    :param source_file_path: string, full path to source file.
    :param target_file_path: string, full path to target file.
    :param no_overwrite: boolean, if 'True', then the function will not overwrite the file if it exists.
    :param preserve_metadata: boolean, if 'True', then the function will try to preserve the metadata of the file.

    :return: None
    """

    # Check if 'no_overwrite' is set to 'True' and if the file exists.
    if no_overwrite:
        if is_file_exists(target_file_path):
            raise FileExistsError(f'File already exists: {target_file_path}')

    # Copy file.
    if preserve_metadata:
        shutil.copy2(source_file_path, target_file_path)
    else:
        shutil.copy(source_file_path, target_file_path)


def copy_directory(source_directory: str, target_directory: str, overwrite: bool = False) -> None:
    """
    The function copies directory from source to target.

    :param source_directory: string, full path to source directory.
    :param target_directory: string, full path to target directory.
    :param overwrite: boolean, if 'True', then the function will overwrite the directory if it exists.

    :return: None
    """

    # Check if 'overwrite' is set to 'True' and if the directory exists.
    if overwrite:
        if is_directory_exists(target_directory):
            remove_directory(target_directory)

    # Copy directory.
    shutil.copytree(source_directory, target_directory)


def copy_files_from_folder_to_folder(source_directory: str, target_directory: str, overwrite: bool = False) -> None:
    """
    The function will copy all the files from source directory to target directory.

    :param source_directory: string, full path to source directory.
    :param target_directory: string, full path to target directory.
    :param overwrite: boolean, if 'True', then the function will overwrite the files if they exist.
    """
    # Make sure the destination directory exists, if not create it
    os.makedirs(target_directory, exist_ok=True)

    # Copy contents of the source directory to the destination directory
    for item in os.listdir(source_directory):
        s = os.path.join(source_directory, item)
        d = os.path.join(target_directory, item)

        if os.path.isdir(s):
            if os.path.exists(d) and not overwrite:
                print(f"Directory {d} already exists. Skipping due to overwrite=False.")
            else:
                shutil.copytree(s, d, dirs_exist_ok=overwrite)
        else:
            if os.path.exists(d) and not overwrite:
                print(f"File {d} already exists. Skipping due to overwrite=False.")
            else:
                shutil.copy2(s, d)


class AtomicPath:
    def __init__(self, path: str):
        self.path: str = path

        self.is_file: bool = os.path.isfile(path)
        self.is_directory: bool = os.path.isdir(path)
        self.name: str = Path(path).name

        self.queried_directory: str = ''
        # noinspection PyTypeChecker
        self.last_modified: float = None
        self.relative_dir: str = ''
        self.binary: bytes = b''
        self.hash: str = ''
        self.datetime_datetime = None
        self.datetime_string: str = ''
        # noinspection PyTypeChecker
        self.datetime_float: float = None
        self.datetime_format: str = ''

    def __str__(self):
        return self.path

    def update(
            self,
            path: str = None,
            datetime_format: str = None,
            update_datetime: bool = False,
            update_last_modified: bool = False,
            update_binary: bool = False,
            update_hash: bool = False
    ):
        if path:
            if path != self.path:
                self.queried_directory = ''
                self.last_modified = None
                self.relative_dir = ''
                self.binary = b''
                self.hash = ''
                self.datetime_datetime = None
                self.datetime_string = ''
                self.datetime_float = None
                self.datetime_format = ''

                self.path = path
                self.is_file = os.path.isfile(path)
                self.is_directory = os.path.isdir(path)
                self.name = Path(path).name

        # Update the datetime format only if it is provided without the update_datetime boolean.
        # Since, we don't want this variable if there is no relation between the datetime format and the filename.
        # If the user want to put it manually, then we will not stop him, but this case is useless if filename
        # doesn't contain the datetime.
        if datetime_format and not update_datetime:
            self.datetime_format = datetime_format

        if update_datetime and not datetime_format and not self.datetime_format:
            raise ValueError('If "update_datetime" is True, then "datetime_format" must be provided.')

        if update_datetime:
            self.datetime_datetime, self.datetime_string, self.datetime_float = (
                datetimes.get_datetime_from_complex_string_by_pattern(self.name, datetime_format))
            # If the provided datetime format is correct, then we will update the datetime format.
            if self.datetime_string:
                self.datetime_format = datetime_format

        if update_last_modified:
            self.last_modified = get_file_modified_time(self.path)

        if update_binary:
            self.binary = file_io.read_file(self.path, file_mode='rb', stdout=False)

        if update_hash:
            if self.binary:
                self.hash = hashing.hash_bytes(self.binary)
            else:
                self.hash = hashing.hash_file(self.path)


def get_paths_from_directory(
        directory_path: str,
        simple_list: bool = False,
        get_file: bool = False,
        get_directory: bool = False,
        recursive: bool = True,
        file_name_check_pattern: str = '*',
        datetime_format: str = None,
        specific_date: str = None,
        add_relative_directory: bool = False,
        relative_file_name_as_directory: bool = False,
        add_last_modified_time: bool = False,
        sort_by_last_modified_time: bool = False,
        add_file_binary: bool = False,
        add_file_hash: bool = False,
) -> Union[list[AtomicPath], list[str]]:
    """
    Recursive, by option.
    The function receives a filesystem directory as string, scans it recursively for files and returns list of
    full paths to that file (including).
    If 'file_name_check_tuple' specified, the function will return only list of files that answer to the input
    of that tuple.

    :param directory_path: string to full path to directory on the filesystem to scan.
    :param simple_list: boolean, if 'True', then the function will return only full file paths.
    :param get_file: boolean, if 'True', then the function will return files.
    :param get_directory: boolean, if 'True', then the function will return directories.
    :param recursive: boolean.
        'True', then the function will scan recursively in subdirectories.
        'False', then the function will scan only in the directory that was passed.
    :param file_name_check_pattern: string, if specified, the function will return only files that match the pattern.
        The string can contain part of file name to check or full file name with extension.
        Can contain wildcards.
    :param datetime_format: datetime format string pattern to match the date in the file name.
        If specified, the function will get the files by the date pattern.

        Example:
        datetime_format = '%Y-%m-%d'
    :param specific_date: Specific date to get the file path.
        If specified, the function will get the file by the specific date.
        Meaning that 'datetime_format' must be specified.
    :param add_relative_directory: boolean, if
        'True', then the function will add relative directory to the output list.
            In this case the output list will contain dictionaries with keys 'path' and 'relative_dir'.
        'False', then the function will not add relative directory to the output list.
            And the output list will contain only full file paths.
    :param relative_file_name_as_directory: boolean that will set if 'relative_directory_list' should contain
        file name with extension for each entry.
    :param add_last_modified_time: boolean, if 'True', then the function will add last modified time of the file
        to the output list.
    :param sort_by_last_modified_time: boolean, if 'True', then the function will sort the output list by last
        modified time of the file.
    :param add_file_binary: boolean, if 'True', then the function will add binary content of the file to each file
        object of the output list.
    :param add_file_hash: boolean, if 'True', then the function will add hash of the file to each file object of the
        output list.

    :return: list of all found filenames with full file paths, list with relative folders to file excluding the
        main folder.
    """

    def get_path(file_or_directory: str):
        """
        Function gets the full file path, adds it to the found 'object_list' and gets the relative path to that
        file, against the main path to directory that was passed to the parent function.
        """

        if strings.match_pattern_against_string(file_name_check_pattern, file_or_directory):
            file_or_dir_path: str = os.path.join(dir_path, file_or_directory)

            if simple_list:
                object_list.append(file_or_dir_path)
                return

            path_object: AtomicPath = AtomicPath(path=file_or_dir_path)
            path_object.queried_directory = directory_path

            if add_relative_directory:
                # if 'relative_file_name_as_directory' was passed.
                if relative_file_name_as_directory:
                    # Output the path with filename.
                    path_object.relative_dir = _get_relative_output_path_from_input_path(
                        directory_path, dir_path, file_or_directory)
                # if 'relative_file_name_as_directory' wasn't passed.
                else:
                    # Output the path without filename.
                    path_object.relative_dir = _get_relative_output_path_from_input_path(
                        directory_path, dir_path)

                # Remove separator from the beginning if exists.
                path_object.relative_dir = path_object.relative_dir.removeprefix(os.sep)

            # If 'add_last_modified_time' was passed.
            if add_last_modified_time:
                # Get last modified time of the file.
                path_object.update(update_last_modified=True)

            if datetime_format:
                # Get the datetime object from the file name by the date format pattern.
                path_object.update(datetime_format=datetime_format, update_datetime=True)
                # If the datetime string is empty, then the file doesn't contain the date in the filename.
                if not path_object.datetime_string:
                    return

            if specific_date:
                if path_object.datetime_string != specific_date:
                    return

            object_list.append(path_object)

    if get_file and get_directory:
        raise ValueError('Parameters "get_file" and "get_directory" cannot be both "True".')
    elif not get_file and not get_directory:
        raise ValueError('Parameters "get_file" and "get_directory" cannot be both "False".')

    if get_directory and (add_file_binary or add_file_hash):
        raise ValueError(
            'While "get_directory" is True, Parameters "add_file_binary" or "add_file_hash" cannot be "True".')

    if sort_by_last_modified_time and not add_last_modified_time:
        raise ValueError('Parameter "sort_by_last_modified_time" cannot be "True" if parameter '
                         '"add_last_modified_time" is not "True".')
    if relative_file_name_as_directory and not add_relative_directory:
        raise ValueError('Parameter "relative_file_name_as_directory" cannot be "True" if parameter '
                         '"add_relative_directory" is not "True".')

    if not datetime_format and specific_date:
        raise ValueError('If "specific_date" is specified, "datetime_format" must be specified.')

    # === Function main ================
    # Define locals.
    object_list: list = list()

    # "Walk" over all the directories and subdirectories - make list of full file paths inside the directory
    # recursively.
    for dir_path, sub_dirs, files in os.walk(directory_path):
        if get_file:
            # Iterate through all the file names that were found in the folder.
            for path in files:
                # If 'file_name_check_pattern' was passed.
                get_path(path)
        elif get_directory:
            # Iterate through all the directory names that were found in the folder.
            for path in sub_dirs:
                get_path(path)

        if not recursive:
            break

    # If 'sort_by_last_modified_time' was passed.
    if sort_by_last_modified_time:
        # Sort the list by last modified time.
        object_list = list_of_classes.sort_by_attributes(object_list, attribute_list=['last_modified'])

    if add_file_binary or add_file_hash:
        if add_file_binary and not add_file_hash:
            prefix_string = 'Reading Binary of File: '
        elif add_file_hash and not add_file_binary:
            prefix_string = 'Reading Hash of File: '
        elif add_file_binary and add_file_hash:
            prefix_string = 'Reading Binary and Hash of File: '
        else:
            prefix_string = 'Reading File: '

        for file_index, file_path in enumerate(object_list):
            print_api.print_status_of_list(
                list_instance=object_list, prefix_string=prefix_string, current_state=(file_index + 1))

            # If 'add_binary' was passed.
            if add_file_binary and file_path.is_file:
                # Get binary content of the file.
                object_list[file_index].binary = file_io.read_file(file_path.path, file_mode='rb', stdout=False)

            # If 'add_file_hash' was passed.
            if add_file_hash and file_path.is_file:
                # Get hash of the file.
                if file_path.binary:
                    object_list[file_index].hash = hashing.hash_bytes(file_path.binary)
                else:
                    object_list[file_index].hash = hashing.hash_file(file_path.path)

    return object_list


def _get_relative_output_path_from_input_path(main_directory: str, file_directory: str, file_name: str = str()):
    # Getting only the path without the starting main directory.
    path_without_main_directory = file_directory.replace(main_directory, '')

    # If 'file_name' wasn't passed, then return relative directory without the file name.
    if not file_name:
        return path_without_main_directory
    # If 'file_name' was passed, then return relative directory with file name.
    else:
        return path_without_main_directory + os.sep + file_name


def _build_relative_output_path(output_path: str, relative_directory: str):
    """
    Function will output the path including the relative directory if 'relative_directory' isn't empty.
    If 'relative_directory', it means that target file is in same directory as starting directory, then we don't
    need to add the filesystem separator.

    :param output_path: string, main full path to output (C:\\folder).
    :param relative_directory: string, only the relative directory (eg: folder2)(eg: folder2\\some_folder)
    :return: if 'relative_directory' is empty, output example: C:\folder.
        if 'relative_directory' isn't empty, eg1: C:\\folder\\folder2, eg2: C:\\folder\\folder2\\some_folder
    """
    if relative_directory:
        return output_path + os.sep + relative_directory
    else:
        return output_path


def _create_relative_output_directory(output_path: str, relative_directory: str) -> str:
    """
    Function creates a folder based on output of function 'build_relative_output_path'.

    :param output_path: see function 'build_relative_output_path'.
    :param relative_directory: see function 'build_relative_output_path'.
    :return: output of function 'build_relative_output_path'.
    """

    path_to_create: str = _build_relative_output_path(output_path, relative_directory)
    create_directory(path_to_create)
    return path_to_create


def get_file_names_from_directory(directory_path: str) -> list:
    """
    The function is non-recursive, returns only file names inside directory.

    :param directory_path: string, of full path to directory you want to return file names of.
    """

    file_list: list = list()
    for (dir_path, sub_dirs, filenames) in os.walk(directory_path):
        file_list.extend(filenames)
        break

    return file_list


def remove_last_separator(directory_path: str) -> str:
    """
    The function removes the last character in 'directory_path' if it is a separator returning the processed string.
    If the last character is not a separator, nothing is happening.

    :param directory_path:
    :return:
    """

    return directory_path.removesuffix(os.sep)


def add_last_separator(filesystem_path: str) -> str:
    """
    The function adds a separator to the end of the path if it doesn't exist.

    :param filesystem_path: string, path to add separator to.
    :return: string, path with separator at the end.
    """

    if not filesystem_path.endswith(os.sep):
        return filesystem_path + os.sep
    else:
        return filesystem_path


def get_files_and_folders(directory_path: str, string_contains: str = str()):
    """
    The function is not recursive.
    The function will get files and folders in given path. Since files and folders in that path are returned as list
    of strings, the count will be for number of strings in the list.
    Meaning, that we can search for string (example: '.py') in each entry in the list and it doesn't really have to be
    a file extension, so the parameter is called 'string_contains' and not 'extension'. You can search for any string
    as well that matches a directory.

    'glob.glob' can also use wildcards as any folder name:
        f'{directory_path}{os.sep}*{os.sep}*{os.sep}*{suffix}'

    :param directory_path:
    :param string_contains: string, can be any string, since files and directories are returned as list of strings.
        You can search for extension '.py' and for any folder name string, like 'end_of_folder_string'.
    :return: integer of number of found items.
    """
    files_folders_list: list = glob.glob(f'{directory_path}{os.sep}*{string_contains}')
    return files_folders_list


def get_file_modified_time(file_or_dir_path: str) -> float:
    """
    The function returns the time of last modification of the file in seconds since the epoch.

    :param file_or_dir_path: string, full path to file or directory.
    :return: float, time of last modification of the file in seconds since the epoch.
    """
    return os.path.getmtime(file_or_dir_path)


def change_last_modified_date_of_file(file_path: str, new_date: float) -> None:
    """
    The function changes the last modified date of the file.

    Example:
    import os
    import time
    file_path = "C:\\Users\\file.txt"
    new_timestamp = time.mktime(time.strptime('2023-10-03 12:00:00', '%Y-%m-%d %H:%M:%S'))
    os.utime(file_path, (new_timestamp, new_timestamp))

    :param file_path: string, full path to file.
    :param new_date: float, time of last modification of the file in seconds since the epoch.
    :return: None.
    """

    os.utime(file_path, (new_date, new_date))


def find_duplicates_by_hash(
        directory_path: str,
        recursive: bool = False,
        add_binary: bool = False,
        raise_on_found: bool = False
) -> tuple[list, list]:
    """
    The function will find duplicates in a directory by hash of the file.

    :param directory_path: string, full path to directory to search for duplicates.
    :param recursive: boolean.
    :param add_binary: boolean, if 'True', then the function will add the binary of the file to the output list.
    :param raise_on_found: boolean, if 'True', then the function will raise an exception if duplicates were found.

    :return: list of all files, list of duplicates
    """

    # Get all the files.
    files: list = get_paths_from_directory(
        directory_path, get_file=True, recursive=recursive, add_file_binary=add_binary)

    same_hash_files: list = list()
    # Check if there are files that have exactly the same hash.
    for atomic_path in files:
        # Create a list of files that have the same hash for current 'firmware'.
        current_run_list: list = list()
        for atomic_path_compare in files:
            # Add all the 'firmware_compare' that have the same hash to the list.
            if (atomic_path.hash == atomic_path_compare.hash and
                    atomic_path.path != atomic_path_compare.path):
                # Check if current 'firmware' is already in the 'same_hash_files' list. If not, add 'firmware_compare'
                # to the 'current_run_list'.
                if not any(list_of_dicts.is_value_exist_in_key(
                        list_of_dicts=test_hash, key='path', value_to_match=atomic_path.path) for
                           test_hash in same_hash_files):
                    current_run_list.append({
                        'path': atomic_path_compare.path,
                        'hash': atomic_path_compare.hash
                    })

        if current_run_list:
            # After the iteration of the 'firmware_compare' finished and the list is not empty, add the 'firmware'
            # to the list.
            current_run_list.append({
                'path': atomic_path.path,
                'hash': atomic_path.hash
            })
            same_hash_files.append(current_run_list)

    # If there are files with the same hash, print them and raise an exception.
    if same_hash_files and raise_on_found:
        # Raise exception for the list of lists.
        message = f'Files with the same hash were found:\n'
        for same_hash in same_hash_files:
            message += f'{same_hash}\n'

        raise ValueError(message)

    return files, same_hash_files


def convert_windows_to_linux_path(
        windows_path: str,
        convert_drive: bool = True,
        add_wsl_mnt: bool = False
) -> str:
    """
    Convert a Windows file path to Linux file path. Add WSL "/mnt/" if specified.

    :param windows_path: The Windows path to convert.
    :param convert_drive: boolean, if 'True', then the function will convert the drive letter to lowercase and
        remove the colon.
    :param add_wsl_mnt: boolean, if 'True', then the function will add '/mnt/' to the beginning of the path.
    :return: The converted WSL file path as a string.

    Usage to convert to WSL path:
        convert_windows_to_linux_path('C:\\Users\\user1\\Downloads\\file.txt', convert_drive=True, add_wsl_mnt=True)
        '/mnt/c/Users/user1/Downloads/file.txt'
    """

    if not convert_drive and add_wsl_mnt:
        raise ValueError('Cannot add WSL mnt without converting drive.')

    # Convert the Windows path to a PurePath object
    windows_path_obj = PureWindowsPath(windows_path)

    if convert_drive:
        # Get drive letter and convert it to lowercase.
        drive = windows_path_obj.drive.lower().replace(':', '')

        # Convert Windows path to Linux path without drive.
        linux_path = PurePosixPath(*windows_path_obj.parts[1:])

        # Add drive to Linux path.
        linux_path = drive / linux_path

        if add_wsl_mnt:
            # Construct WSL path
            linux_path = PurePosixPath('/mnt') / linux_path
    else:
        # Convert Windows path to Linux path
        linux_path = windows_path_obj.as_posix()

    return str(linux_path)


def get_directory_size(directory_path: str):
    """
    The function returns the size of the directory in bytes.
    This is one of the fastest ways to get the size of a directory.

    :param directory_path:
    :return:
    """

    total_size = 0
    with os.scandir(directory_path) as it:
        for entry in it:
            if entry.is_file():
                total_size += entry.stat().st_size
            elif entry.is_dir():
                total_size += get_directory_size(entry.path)
    return total_size


def get_subpaths_between(start_path: str, end_path: str) -> list[str]:
    # noinspection GrazieInspection
    """
        Get the subpaths between two paths.
        :param start_path: string, start path.
        :param end_path: string, end path.
        :return:

        Example Linux:
            start_path = '/test/1'
            end_path = '/test/1/2/3/4'

            subpaths = get_subpaths_between(start_path, end_path)

            subpaths = [
                '/test/1'
                '/test/1/2',
                '/test/1/2/3',
                '/test/1/2/3/4',
            ]


        Example Windows:
            start_path = 'C:\\test\\1'
            end_path = 'C:\\test\\1\\2\\3\\4'

            subpaths = get_subpaths_between(start_path, end_path)

            subpaths = [
                'C:\\test\\1',
                'C:\\test\\1\\2',
                'C:\\test\\1\\2\\3',
                'C:\\test\\1\\2\\3\\4',
            ]
        """

    # Detect slash type based on the input (default to forward slash)
    slash_type = "\\" if "\\" in start_path else "/"

    # Normalize the paths to use forward slashes for processing
    start_path = start_path.replace("\\", "/")
    end_path = end_path.replace("\\", "/")

    if not end_path.startswith(start_path):
        raise ValueError("Start path must be a prefix of the end path")

    # Get the remainder of the end path after the start path.
    remainder = end_path[len(start_path):].strip("/")
    parts = remainder.split("/")

    # Construct the subpaths having the start path as the first element.
    subpaths = [start_path.replace("/", slash_type)]
    current_path = start_path
    for part in parts:
        if part:  # Avoid empty parts
            current_path += "/" + part  # Use forward slash for processing
            # Convert the path back to the original slash type before adding
            subpaths.append(current_path.replace("/", slash_type))

    return subpaths

    # start = Path(start_path).resolve()
    # end = Path(end_path).resolve()
    # subpaths = []
    #
    # # Ensure start is a parent of end
    # if start in end.parents:
    #     current = end
    #     while current != start:
    #         subpaths.append(current)
    #         current = current.parent
    #     subpaths.append(str(start))  # Optionally add the start path itself
    # else:
    #     raise ValueError("Start path must be a parent of the end path")
    #
    # # Reverse the list, so it goes from start to end.
    # subpaths.reverse()
    #
    # return subpaths


def create_dict_of_paths_list(list_of_paths: list) -> list:
    """
    The function receives a list of paths and returns a dictionary with keys as the paths and values as the
    subpaths of the key path.

    Example:
        list_of_paths = [
            "/test1/test2/3/4/5/file1.txt",
            "/test1/test2/file2.txt",
            "/test1/test2/3/file3.txt",
            "/test1/test2/3/4/5/file4.txt"
        ]

        structure = create_dict_of_paths_list(list_of_paths)

        structure = {
            "test1": {
                "test2": {
                    "3": {
                        "4": {
                            "5": {
                                0: "file1.txt",
                                1: "file4.txt"
                            }
                        },
                        0: "file3.txt"
                    },
                    0: "file2.txt"
                }
            }
        }

    :param list_of_paths: list of strings, paths.
    :return: dictionary.
    """

    structure: list = []
    for path in list_of_paths:
        create_dict_of_path(path, structure)
    return structure


def create_dict_of_path(
        path: str,
        structure_list: list,
        add_data_to_entry: list[dict[str, any]] = None
):
    """
    The function receives a path and a list, and adds the path to the list.
    Check the working example from 'create_dict_of_paths_list' function.

    :param path: string, path.
    :param structure_list: list to add the path to.
    :param add_data_to_entry: a list of dicts with data to add to the entry.
        dict format: {key: data}
    :return:
    """

    # Normalize path for cross-platform compatibility
    normalized_path = path.replace("\\", "/")
    parts = normalized_path.strip("/").split("/")

    current_level = structure_list

    for i, part in enumerate(parts):
        # Determine if this is the last part (a file or final component of the path)
        is_last_part = (i == len(parts) - 1)

        # Try to find an existing entry for this part
        existing_entry = next((item for item in current_level if item["entry"] == part), None)

        if existing_entry is None:
            # Create a new entry
            new_entry = {"entry": part, "included": []}

            # Add additional data if it's the last part
            if is_last_part and add_data_to_entry:
                for data_dict in add_data_to_entry:
                    new_entry.update(data_dict)

            current_level.append(new_entry)

            # Only update current_level if it's not the last part
            if not is_last_part:
                current_level = new_entry["included"]
        else:
            # If the entry exists and it's not the last part, navigate deeper
            if not is_last_part:
                current_level = existing_entry["included"]

            # If the entry exists and it's the last part, update with additional data
            if is_last_part and add_data_to_entry:
                for data_dict in add_data_to_entry:
                    existing_entry.update(data_dict)


def list_open_files_in_directory(directory):
    """
    The function lists all open files by any processes in the directory.
    :param directory:
    :return:
    """
    open_files: list = []

    # Iterate over all running processes
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # List open files for the process
            proc_open_files = proc.open_files()
            for file in proc_open_files:
                if file.path.startswith(directory):
                    # noinspection PyUnresolvedReferences
                    open_files.append((proc.info['pid'], proc.info['name'], file.path))
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            # Ignore processes that can't be accessed
            continue

    return open_files


def is_any_file_in_directory_opened_by_process(directory_path: str) -> bool:
    """
    The function checks if any file in the directory is opened in any process using psutil.

    :param directory_path: string, full path to directory.
    :return: boolean, if 'True', then at least one file in the directory is opened by a process.
    """

    # for filename in os.listdir(directory_path):
    #     file_path = os.path.join(directory_path, filename)
    #     if os.path.isfile(file_path):
    #         return is_file_locked(file_path)
    # return False

    # Iterate over all running processes
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # List open files for the process
            proc_open_files = proc.open_files()
            for file in proc_open_files:
                if file.path.startswith(directory_path):
                    return True
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            # Ignore processes that can't be accessed
            continue

    return False


def is_any_file_in_list_open_by_process(file_paths_list: list[str]) -> bool:
    """
    The function checks if any file in the list is opened by any running process.

    :param file_paths_list: list of strings, full paths to files.
    :return: boolean, if 'True', then at least one file in the list is locked.
    """

    for file_path in file_paths_list:
        if is_file_open_by_process(file_path):
            return True
    return False


def is_file_open_by_process(file_path: str) -> bool:
    """
    The function checks if the file is opened in any of the running processes.

    :param file_path: string, full path to file.
    :return: boolean, if 'True', then the file is locked.
    """

    # If the file doesn't exist, or it is not a file, it's not locked.
    if not os.path.isfile(file_path):
        return False

    # Iterate over all running processes
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # List open files for the process
            proc_open_files = proc.open_files()
            for file in proc_open_files:
                if file.path == file_path:
                    return True
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            # Ignore processes that can't be accessed
            continue

    return False


def get_download_directory(
        place: Literal[
            'temp',
            'script',
            'working'] = 'temp',
        script_path: str = None
) -> str:
    """
    The function returns the default download directory based on place.

    :param place: string,
        'temp', then the function will return the temporary directory.
        'script', then the function will return the directory of the script.
        'working', then the function will return the working directory.
    :param script_path: string, full path to the script.
    :return: string, full path to the default download directory.
    """

    if place == 'script' and script_path is None:
        raise ValueError("Script path must be specified if place is 'script'.")

    # Get the download directory based on the operating system
    if place == 'script':
        download_directory = get_file_directory(script_path)
    elif place == 'working':
        download_directory = get_working_directory()
    elif place == 'temp':
        download_directory = get_temp_directory()
    else:
        raise ValueError("Invalid place specified.")

    return download_directory


def backup_folder(directory_path: str, backup_directory: str) -> None:
    """
    Backup the specified directory.

    :param directory_path: The directory path to back up.
    :param backup_directory: The directory to back up the directory to.

    Example:
    backup_folder(
        directory_path='C:\\Users\\user1\\Downloads\\folder1', backup_directory='C:\\Users\\user1\\Downloads\\backup')

    Backed up folder will be moved to 'C:\\Users\\user1\\Downloads\\backup' with timestamp in the name.
    Final path will look like: 'C:\\Users\\user1\\Downloads\\backup\\20231003-120000-000000_folder1'
    """

    if is_directory_exists(directory_path):
        timestamp: str = datetimes.TimeFormats().get_current_formatted_time_filename_stamp(True)
        directory_name = Path(directory_path).name
        backup_directory_path: str = str(Path(backup_directory) / f"{timestamp}_{directory_name}")
        create_directory(backup_directory_path)
        move_folder(directory_path, backup_directory_path)


def backup_file(
        file_path: str,
        backup_directory: str,
        timestamp_as_prefix: bool = False
) -> Union[str, None]:
    """
    Backup the specified file.

    :param file_path: The file path to back up.
    :param backup_directory: The directory to back up the file to.
    :param timestamp_as_prefix: boolean, if
        True, then the timestamp will be added as a prefix to the file name.
        False, then the timestamp will be added as a suffix to the file name.
    -----------------------------------------
    Example:
    backup_file(
        file_path='C:\\Users\\user1\\Downloads\\file.txt',
        backup_directory='C:\\Users\\user1\\Downloads\\backup',
        timestamp_as_prefix=True
    )

    Backed up file will be moved to 'C:\\Users\\user1\\Downloads\\backup' with timestamp in the name.
    Final path will look like: 'C:\\Users\\user1\\Downloads\\backup\\20231003-120000-000000_file.txt'
    ---------------------------------------------
    Example when timestamp_as_prefix is False:
    backup_file(
        file_path='C:\\Users\\user1\\Downloads\\file.txt',
        backup_directory='C:\\Users\\user1\\Downloads\\backup',
        timestamp_as_prefix=False
    )

    Backed up file will be moved to 'C:\\Users\\user1\\Downloads\\backup' with timestamp in the name.
    Final path will look like: 'C:\\Users\\user1\\Downloads\\backup\\file_20231003-120000-000000.txt'
    """

    if is_file_exists(file_path):
        timestamp: str = datetimes.TimeFormats().get_current_formatted_time_filename_stamp(True)
        file_name_no_extension = Path(file_path).stem
        file_extension = Path(file_path).suffix
        if timestamp_as_prefix:
            file_name: str = f"{timestamp}_{file_name_no_extension}{file_extension}"
        else:
            file_name: str = f"{file_name_no_extension}_{timestamp}{file_extension}"
        backup_file_path: str = str(Path(backup_directory) / file_name)
        rename_file(file_path, file_name)

        return backup_file_path
    else:
        return None


def find_file(file_name: str, directory_path: str):
    """
    The function finds the file in the directory recursively.
    :param file_name: string, The name of the file to find.
    :param directory_path: string, The directory to search in.
    :return:
    """
    for dir_path, dir_names, filenames in os.walk(directory_path):
        for filename in filenames:
            if filename == file_name:
                return os.path.join(dir_path, filename)
    return None


def create_ubuntu_desktop_shortcut(
        file_path: str = None,
        shortcut_name: str = None,
        command: str = None,
        working_directory: str = None,
        icon_path: str = None,
        terminal: bool = False,
        comment: str = "Shortcut to execute the Python script",
        categories: str = "Utility",
        set_executable: bool = False,
        set_trusted: bool = False,
        set_xfce_exe_checksum: bool = False
):
    """
    Create a desktop shortcut on Ubuntu.
    Either file_path or command must be specified.

    :param file_path: string, The file_path to execute when the shortcut is clicked.
        Example2: '/path/to/script.sh'
    :param shortcut_name: string, The name of the shortcut.
        Example: 'My Python Script'
        Result: 'My Python Script.desktop'
    :param command: string, The command to execute when the shortcut is clicked.
        Example: 'python3 /path/to/script.py'
    :param working_directory: string, The working directory for the command.
        If None, the command will be executed in the same script's directory.
    :param icon_path: string, The path to the icon file.
    :param terminal: boolean, If True, the command will be executed in a terminal.
    :param comment: string, A comment to describe the shortcut.
    :param categories: string, The categories of the shortcut.
    :param set_executable: boolean, If True, the shortcut will be made executable.
    :param set_trusted: boolean, If True, the shortcut will be marked as trusted.
        This is needed for GNOME.
    :param set_xfce_exe_checksum: boolean, If True, the shortcut will be made safe executable for XFCE.

    :return: None
    """

    if not file_path and not command:
        raise ValueError("Either 'file_path' or 'command' must be specified.")
    if command and file_path:
        raise ValueError("Only one of 'file_path' or 'command' can be specified.")
    if command and not shortcut_name:
        raise ValueError("The 'shortcut_name' must be specified when 'command' is used.")

    from .permissions import ubuntu_permissions

    # Get the user's directory.
    desktop_dir = os.path.expanduser("~/Desktop")

    if not working_directory and file_path:
        working_directory = os.path.dirname(file_path)

    if not shortcut_name:
        shortcut_name: str = Path(file_path).stem

    if command:
        executable: str = command
    elif file_path:
        executable: str = file_path
    else:
        raise ValueError("Either 'file_path' or 'command' must be specified.")

    # Full path to the .desktop file
    shortcut_path = os.path.join(desktop_dir, f"{shortcut_name}.desktop")

    # Generate the content for the .desktop file
    desktop_entry = [
        "[Desktop Entry]",
        "Version=1.0",
        "Type=Application",
        f"Name={shortcut_name}",
        f"Exec={executable}",
        f"Path={working_directory}" if working_directory else "",
        f"Icon={icon_path}" if icon_path else "",
        f"Terminal={'true' if terminal else 'false'}",
        f"Comment={comment}",
        f"Categories={categories};",
    ]

    # Write the .desktop file
    with open(shortcut_path, "w") as shortcut_file:
        shortcut_file.write("\n".join(line for line in desktop_entry if line))  # Skip empty lines

    # Make the .desktop file executable
    if set_executable:
        ubuntu_permissions.set_executable(shortcut_path)

    # Mark the .desktop file as trusted
    if set_trusted:
        ubuntu_permissions.set_trusted_executable(shortcut_path)

    # Make the .desktop file safe executable for XFCE
    if set_xfce_exe_checksum:
        ubuntu_permissions.set_xfce_exe_checksum(shortcut_path)

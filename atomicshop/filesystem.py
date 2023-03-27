# v1.0.5 - 21.03.2023 13:20
import os
import pathlib
from pathlib import Path
import glob
import shutil
from enum import Enum

from .print_api import print_api


def get_file_directory(file_path: str) -> str:
    """
    The function will return directory of the file.

    :param file_path: string, full file path.
    :return: string.
    """
    return str(Path(file_path).parent)


def get_working_directory() -> str:
    """
    The function returns working directory of called script file.

    :return: string.
    """
    return str(Path.cwd())


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
        return f'{full_path_to_add}{os.sep}{remove_first_separator(filesystem_path)}'
    else:
        return filesystem_path


def check_file_existence(file_path: str) -> bool:
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


def check_directory_existence(directory_path: str) -> bool:
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
        print_api(f'File Removed: {file_path}')
        return True
    # Since the file doesn't exist, we actually don't care, since we want to remove it anyway.
    except FileNotFoundError:
        message = f'File Removal Failed, File non-existent: {file_path}'
        print_api(message, error_type=True, logger_method='critical', **kwargs)
        return False


def create_folder(directory_fullpath: str):
    # Create folder if non-existent.
    # The library is used to create folder if it doesn't exist and won't raise exception if it does
    # 'parents=True' will create also the parent folders of the last folder, not used in our case
    # 'exist_ok=True' if the folder exists, then it is ok.
    pathlib.Path(directory_fullpath).mkdir(parents=True, exist_ok=True)


def move_files_from_folder_to_folder(source_directory: str, target_directory: str):
    """
    The function is currently non-recursive and not tested with directories inside the source directories.
    """

    # Get all file names without full paths in source folder.
    file_list_in_source: list = get_file_names_from_directory(source_directory)

    # Iterate through all the files.
    for file_name in file_list_in_source:
        # Move the file from source to target.
        shutil.move(source_directory + os.sep + file_name, target_directory + os.sep + file_name)


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


class ComparisonOperator(Enum):
    """
    Enum class that was created for 'scan_directory_and_return_list' function.
    Specifically for 'file_name_check_tuple[1]' - second entry.
    """
    EQ = '__eq__'
    CONTAINS = '__contains__'


def get_file_paths_and_relative_directories(directory_fullpath: str,
                                            file_name_check_tuple: tuple = tuple(),
                                            relative_file_name_as_directory: bool = False):
    """
    The function receives a filesystem directory as string, scans it recursively for files and returns list of
    full paths to that file (including).
    If 'file_name_check_tuple' specified, the function will return only list of files that answer to the input
    of that tuple.
    Recursive.

    :param directory_fullpath: string to full path to directory on the filesystem to scan.
    :param file_name_check_tuple: tuple that should contain 2 entries:
        file_name_check_tuple[0]: string that will contain part of file name to check or full file name with extension.
        file_name_check_tuple[1]: 'ComparisonOperator' object to test against found file name with extension.
            'ComparisonOperator.EQ' will check for specific file name (eg: 'config_file.ini').
            'ComparisonOperator.CONTAINS' will check if file name contains part of the string (eg: 'config')(eg: '.ini')
    :param relative_file_name_as_directory: boolean that will set if 'relative_directory_list' should contain
        file name with extension for each entry.
    :return: list of all found filenames with full file paths, list with relative folders to file excluding the
        main folder.
    """

    def get_file():
        """
        Function gets the full file path, adds it to the found 'object_list' and gets the relative path to that
        file, against the main path to directory that was passed to the parent function.
        """
        # Get full file path of the file.
        file_path = os.path.join(dirpath, file)
        object_list.append(file_path)

        # if 'relative_file_name_as_directory' was passed.
        if relative_file_name_as_directory:
            # Output the path with filename.
            relative_directory = _get_relative_output_path_from_input_path(directory_fullpath, dirpath, file)
        # if 'relative_file_name_as_directory' wasn't passed.
        else:
            # Output the path without filename.
            relative_directory = _get_relative_output_path_from_input_path(directory_fullpath, dirpath)

        # Remove separator from the beginning if exists.
        relative_directory = relative_directory.removeprefix(os.sep)

        relative_paths_list.append(relative_directory)

    # Type checking.
    if file_name_check_tuple:
        if not isinstance(file_name_check_tuple[1], ComparisonOperator):
            raise TypeError(f'Second entry of tuple "file_name_check_tuple" is not of "ComparisonOperator" type.')

    # === Function main ================
    # Define locals.
    object_list: list = list()
    relative_paths_list: list = list()

    # "Walk" over all the directories and subdirectories - make list of full file paths inside the directory
    # recursively.
    for dirpath, subdirs, files in os.walk(directory_fullpath):
        # Iterate through all the file names that were found in the folder.
        for file in files:
            # If 'file_name_check_tuple' was passed.
            if file_name_check_tuple:
                # Get separate variables from the tuple.
                # 'check_string' is a string that will be checked against 'file' iteration, which also a string.
                # 'comparison_operator' is 'ComparisonOperator' Enum object, that contains the string method
                # operator that will be used against the 'check_string'.
                check_string, comparison_operator = file_name_check_tuple
                # 'getattr' adds the string comparison method to the 'file' string. Example:
                # file.__eq__
                # 'comparison_operator' is the Enum class representation and '.value' method is the string
                # representation of '__eq__'.
                # and after that comes the check string to check against:
                # file.__eq__(check_string)
                if getattr(file, comparison_operator.value)(check_string):
                    get_file()
            # If 'file_name_check_tuple' wasn't passed, then get all the files.
            else:
                get_file()

    return object_list, relative_paths_list


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
    create_folder(path_to_create)
    return path_to_create


def remove_last_separator(directory_path: str) -> str:
    """
    The function removes the last character in 'directory_path' if it is a separator returning the processed string.
    If the last character is not a separator, nothing is happening.

    :param directory_path:
    :return:
    """

    return directory_path.removesuffix(os.sep)


def remove_first_separator(filesystem_path: str) -> str:
    """
    The function removes the first character in 'filesystem_path' if it is a separator returning the processed string.
    If the first character is not a separator, nothing is happening.

    :param filesystem_path:
    :return:
    """
    return filesystem_path.removesuffix(os.sep)


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

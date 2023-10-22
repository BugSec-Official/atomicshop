import os
import pathlib
from pathlib import Path, PurePath, PureWindowsPath
import glob
import shutil

from .print_api import print_api, print_status_of_list
from .basics import strings, list_of_dicts
from .file_io import file_io
from . import hashing


def get_working_directory() -> str:
    """
    The function returns working directory of called script file.
    If the function is placed in other file and is called from the main script, it will return
    the main script directory and not the file that the function is in.

    :return: string.
    """
    return str(Path.cwd())


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


def get_file_name(file_path: str) -> str:
    """
    The function will return file name of the file.

    :param file_path: string, full file path.
    :return: string.
    """
    return str(Path(file_path).name)


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


def create_directory(directory_fullpath: str):
    # Create directory if non-existent.
    # The library is used to create folder if it doesn't exist and won't raise exception if it does
    # 'parents=True' will create also the parent folders of the last folder, not used in our case
    # 'exist_ok=True' if the folder exists, then it is ok.
    pathlib.Path(directory_fullpath).mkdir(parents=True, exist_ok=True)


def move_file(source_file_path: str, target_file_path: str, no_overwrite: bool = False) -> None:
    """
    The function moves file from source to target.

    :param source_file_path: string, full path to source file.
    :param target_file_path: string, full path to target file.
    :param no_overwrite: boolean, if 'True', then the function will not overwrite the file if it exists.

    :return: None
    """

    # Check if 'no_overwrite' is set to 'True' and if the file exists.
    if no_overwrite:
        if check_file_existence(target_file_path):
            raise FileExistsError(f'File already exists: {target_file_path}')

    # Move file.
    shutil.move(source_file_path, target_file_path)


def move_files_from_folder_to_folder(source_directory: str, target_directory: str):
    """
    The function is currently non-recursive and not tested with directories inside the source directories.
    The function will move all the files from source directory to target directory overwriting existing files.
    """

    # Get all file names without full paths in source folder.
    file_list_in_source: list = get_file_names_from_directory(source_directory)

    # Iterate through all the files.
    for file_name in file_list_in_source:
        # Move the file from source to target.
        move_file(source_directory + os.sep + file_name, target_directory + os.sep + file_name)


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
        if check_file_existence(target_file_path):
            raise FileExistsError(f'File already exists: {target_file_path}')

    # Copy file.
    if preserve_metadata:
        shutil.copy2(source_file_path, target_file_path)
    else:
        shutil.copy(source_file_path, target_file_path)


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


def get_file_paths_and_relative_directories(
        directory_fullpath: str,
        recursive: bool = True,
        file_name_check_pattern: str = '*',
        relative_file_name_as_directory: bool = False,
        add_last_modified_time: bool = False,
        sort_by_last_modified_time: bool = False
):
    """
    Recursive, by option.
    The function receives a filesystem directory as string, scans it recursively for files and returns list of
    full paths to that file (including).
    If 'file_name_check_tuple' specified, the function will return only list of files that answer to the input
    of that tuple.

    :param directory_fullpath: string to full path to directory on the filesystem to scan.
    :param recursive: boolean.
        'True', then the function will scan recursively in subdirectories.
        'False', then the function will scan only in the directory that was passed.
    :param file_name_check_pattern: string, if specified, the function will return only files that match the pattern.
        The string can contain part of file name to check or full file name with extension.
        Can contain wildcards.
    :param relative_file_name_as_directory: boolean that will set if 'relative_directory_list' should contain
        file name with extension for each entry.
    :param add_last_modified_time: boolean, if 'True', then the function will add last modified time of the file
        to the output list.
    :param sort_by_last_modified_time: boolean, if 'True', then the function will sort the output list by last
        modified time of the file.

    :return: list of all found filenames with full file paths, list with relative folders to file excluding the
        main folder.
    """

    def get_file():
        """
        Function gets the full file path, adds it to the found 'object_list' and gets the relative path to that
        file, against the main path to directory that was passed to the parent function.
        """

        file_result: dict = dict()

        # Get full file path of the file.
        file_result['path'] = os.path.join(dirpath, file)

        # if 'relative_file_name_as_directory' was passed.
        if relative_file_name_as_directory:
            # Output the path with filename.
            file_result['relative_dir'] = _get_relative_output_path_from_input_path(directory_fullpath, dirpath, file)
        # if 'relative_file_name_as_directory' wasn't passed.
        else:
            # Output the path without filename.
            file_result['relative_dir'] = _get_relative_output_path_from_input_path(directory_fullpath, dirpath)

        # Remove separator from the beginning if exists.
        file_result['relative_dir'] = file_result['relative_dir'].removeprefix(os.sep)

        # If 'add_last_modified_time' was passed.
        if add_last_modified_time:
            # Get last modified time of the file.
            file_result['last_modified'] = get_file_modified_time(file_result['path'])

        object_list.append(file_result)

    if sort_by_last_modified_time and not add_last_modified_time:
        raise ValueError('Parameter "sort_by_last_modified_time" cannot be "True" if parameter '
                         '"add_last_modified_time" is not "True".')

    # === Function main ================
    # Define locals.
    object_list: list = list()

    # "Walk" over all the directories and subdirectories - make list of full file paths inside the directory
    # recursively.
    for dirpath, subdirs, files in os.walk(directory_fullpath):
        # Iterate through all the file names that were found in the folder.
        for file in files:
            # If 'file_name_check_pattern' was passed.
            if strings.match_pattern_against_string(file_name_check_pattern, file):
                get_file()

        if not recursive:
            break

    # If 'sort_by_last_modified_time' was passed.
    if sort_by_last_modified_time:
        # Sort the list by last modified time.
        object_list = list_of_dicts.sort_by_keys(object_list, key_list=['last_modified'])

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


def get_file_modified_time(file_path: str) -> float:
    """
    The function returns the time of last modification of the file in seconds since the epoch.

    :param file_path: string, full path to file.
    :return: float, time of last modification of the file in seconds since the epoch.
    """
    return os.path.getmtime(file_path)


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


def find_duplicates_by_hash(directory_path: str, add_binary: bool = False) -> tuple[list, list]:
    """
    The function will find duplicates in a directory by hash of the file.
    The function is not recursive.

    :param directory_path: string, full path to directory to search for duplicates.
    :param add_binary: boolean, if 'True', then the function will add the binary of the file to the output list.

    :return: list of duplicates, list of all files.
    """

    # Get all the files.
    file_paths_list = get_file_paths_and_relative_directories(directory_path, recursive=False)

    # Create a list of dictionaries, each dictionary is a file with its hash.
    files: list = list()
    for file_index, file_path in enumerate(file_paths_list):
        print_status_of_list(
            list_instance=file_paths_list, prefix_string=f'Reading File: ', current_state=(file_index + 1))

        file_info: dict = dict()
        file_info['file_path'] = file_path['path']

        if add_binary:
            file_info['binary'] = file_io.read_file(file_path['path'], file_mode='rb', stdout=False)
            file_info['file_hash'] = hashing.hash_bytes(file_info['binary'])
        else:
            file_info['file_hash'] = hashing.hash_file(file_path['path'])

        files.append(file_info)

    same_hash_files: list = list()
    # Check if there are files that have exactly the same hash.
    for file_dict in files:
        # Create a list of files that have the same hash for current 'firmware'.
        current_run_list: list = list()
        for file_dict_compare in files:
            # Add all the 'firmware_compare' that have the same hash to the list.
            if (file_dict['file_hash'] == file_dict_compare['file_hash'] and
                    file_dict['file_path'] != file_dict_compare['file_path']):
                # Check if current 'firmware' is already in the 'same_hash_files' list. If not, add 'firmware_compare'
                # to the 'current_run_list'.
                if not any(list_of_dicts.is_value_exist_in_key(
                        list_of_dicts=test_hash, key='file_path', value_to_match=file_dict['file_path']) for
                           test_hash in same_hash_files):
                    current_run_list.append({
                        'file_path': file_dict_compare['file_path'],
                        'file_hash': file_dict_compare['file_hash']
                    })

        if current_run_list:
            # After the iteration of the 'firmware_compare' finished and the list is not empty, add the 'firmware'
            # to the list.
            current_run_list.append({
                'file_path': file_dict['file_path'],
                'file_hash': file_dict['file_hash']
            })
            same_hash_files.append(current_run_list)

    return same_hash_files, files

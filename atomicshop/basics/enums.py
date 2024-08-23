from enum import Enum
import os


class ComparisonOperator(Enum):
    """
    Enum class that was created for 'scan_directory_and_return_list' function.
    Specifically for 'file_name_check_tuple[1]' - second entry.
    """
    EQ = '__eq__'
    CONTAINS = '__contains__'


def __comparison_usage_example(
        directory_fullpath: str,
        file_name_check_tuple: tuple = tuple()):
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

    :return: list of all found filenames with full file paths, list with relative folders to file excluding the
        main folder.

    Usage:
        from atomicshop.filesystem import get_paths_from_directory, ComparisonOperator

        # Get full paths of all the 'engine_config.ini' files.
        engine_config_path_list = get_paths_from_directory(
            directory_fullpath=some_directory_path,
            file_name_check_tuple=(config_file_name, ComparisonOperator.EQ))
    """

    # Type checking.
    if file_name_check_tuple:
        if not isinstance(file_name_check_tuple[1], ComparisonOperator):
            raise TypeError(f'Second entry of tuple "file_name_check_tuple" is not of "ComparisonOperator" type.')

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
                    return
            # If 'file_name_check_tuple' wasn't passed, then get all the files.
            else:
                return

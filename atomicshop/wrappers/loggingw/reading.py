import os
from typing import Literal
from pathlib import Path

from ... import filesystem, datetimes
from ...file_io import csvs


def get_logs_paths(
        log_files_directory_path: str = None,
        log_file_path: str = None,
        pattern: str = '*.*',
        log_type: Literal['csv'] = 'csv',
        latest_only: bool = False,
        previous_day_only: bool = False
):
    """
    This function gets the logs file paths from the directory. Supports rotating files to get the logs by time.

    :param log_files_directory_path: Path to the log files. If specified, the function will get all the files from the
        directory by the 'pattern'.
    :param log_file_path: Path to the log file. If specified, the function will get the file and all the rotated logs
        associated with this file. The 'pattern' will become the file name using the file name and extension.

        Example:
        log_file_path = 'C:/logs/test_log.csv'

        # The function will get all the files that start with 'test_log' and have '.csv' extension:
        pattern = 'test_log*.csv'

        # The 'log_files_directory_path' will also be taken from the 'log_file_path':
        log_files_directory_path = 'C:/logs'
    :param pattern: Pattern to match the log files names.
        Default pattern will match all the files.
    :param log_type: Type of log to get.
    :param latest_only: Boolean, if True, only the latest log file path will be returned.
    :param previous_day_only: Boolean, if True, only the log file path from the previous day will be returned.
    """

    if not log_files_directory_path and not log_file_path:
        raise ValueError('Either "log_files_directory_path" or "log_file_path" must be specified.')
    elif log_files_directory_path and log_file_path:
        raise ValueError('Both "log_files_directory_path" and "log_file_path" cannot be specified at the same time.')

    if log_type != 'csv':
        raise ValueError('Only "csv" log type is supported.')

    if latest_only and previous_day_only:
        raise ValueError('Both "latest_only" and "previous_day_only" cannot be True at the same time.')

    # If log file path is specified, get the pattern from the file name.
    if log_file_path:
        # Build the pattern.
        log_file_name: str = Path(log_file_path).stem
        log_file_extension: str = Path(log_file_path).suffix
        pattern = f'{log_file_name}*{log_file_extension}'

        # Get the directory path from the file path.
        log_files_directory_path = Path(log_file_path).parent

    # Get all the log file paths by the pattern.
    logs_files: list = filesystem.get_file_paths_from_directory(
        log_files_directory_path, file_name_check_pattern=pattern,
        add_last_modified_time=True, sort_by_last_modified_time=True)

    if latest_only:
        logs_files = [logs_files[-1]]

    if previous_day_only:
        # Check if there is a previous day log file.
        if len(logs_files) == 1:
            logs_files = []
        else:
            logs_files = [logs_files[-2]]

    return logs_files


def get_logs(
        log_files_directory_path: str = None,
        log_file_path: str = None,
        pattern: str = '*.*',
        log_type: Literal['csv'] = 'csv',
        header_type_of_files: Literal['first', 'all'] = 'first',
        remove_logs: bool = False,
        move_to_path: str = None,
        print_kwargs: dict = None
):
    """
    This function gets the logs from the log files. Supports rotating files to get the logs by time.

    :param log_files_directory_path: Path to the log files. Check the 'get_logs_paths' function for more details.
    :param log_file_path: Path to the log file. Check the 'get_logs_paths' function for more details.
    :param pattern: Pattern to match the log files names.
        Default pattern will match all the files.
    :param log_type: Type of log to get.
    :param header_type_of_files: Type of header to get from the files.
        'first' - Only the first file has a header for CSV. This header will be used for the rest of the files.
        'all' - Each CSV file has a header. Get the header from each file.
    :param remove_logs: Boolean, if True, the logs will be removed after getting them.
    :param move_to_path: Path to move the logs to.

    :param print_kwargs: Keyword arguments dict for 'print_api' function.
    """

    if not print_kwargs:
        print_kwargs = dict()

    if remove_logs and move_to_path:
        raise ValueError('Both "remove_logs" and "move_to_path" cannot be True/specified at the same time.')

    if header_type_of_files not in ['first', 'all']:
        raise ValueError('Only "first" and "all" header types are supported.')

    # Get all the log file paths by the pattern.
    logs_files: list = get_logs_paths(
        log_files_directory_path=log_files_directory_path, log_file_path=log_file_path,
        pattern=pattern, log_type=log_type)

    # Read all the logs.
    logs_content: list = list()
    header = None
    for single_file in logs_files:
        if log_type == 'csv':
            if header_type_of_files == 'all':
                csv_content, _ = csvs.read_csv_to_list_of_dicts_by_header(single_file['file_path'], **print_kwargs)
                logs_content.extend(csv_content)
            elif header_type_of_files == 'first':
                # The function gets empty header to read it from the CSV file, the returns the header that it read.
                # Then each time the header is fed once again to the function.
                csv_content, header = csvs.read_csv_to_list_of_dicts_by_header(single_file['file_path'], header=header, **print_kwargs)
                # Any way the first file will be read with header.
                logs_content.extend(csv_content)

                # if not header:
                #     # Get the first line of the file as text, which is the header.
                #     header = csvs.get_header(single_file, **print_kwargs)

    if remove_logs:
        # Remove the statistics files.
        for single_file in logs_files:
            filesystem.remove_file(single_file['file_path'])

    if move_to_path:
        # Get formatted time stamp for file name.
        time_stamp = datetimes.TimeFormats().get_current_formatted_time_filename_stamp()
        # Remove last separator from path if it exists.
        move_to_path_with_timestamp = filesystem.remove_last_separator(move_to_path)
        # Add time stamp to path.
        move_to_path_with_timestamp = f'{move_to_path_with_timestamp}{os.sep}{time_stamp}'
        # Create the path.
        filesystem.create_directory(move_to_path_with_timestamp)
        # Move the statistics files.
        for single_file in logs_files:
            single_file_name = filesystem.get_file_name(single_file['file_path'])
            move_to_path_with_file = f'{move_to_path_with_timestamp}{os.sep}{single_file_name}'
            filesystem.move_file(single_file['file_path'], move_to_path_with_file)

    return logs_content

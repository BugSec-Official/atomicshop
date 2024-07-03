import os
from typing import Literal, Union
from pathlib import Path

from ... import filesystem, datetimes
from ...file_io import csvs


READING_EXISTING_LINES: list = []
EXISTING_LOGS_FILE_COUNT: int = 0


def get_logs_paths(
        log_files_directory_path: str = None,
        log_file_path: str = None,
        file_name_pattern: str = '*.*',
        date_pattern: str = None,
        log_type: Literal['csv'] = 'csv',
        latest_only: bool = False,
        previous_day_only: bool = False
):
    """
    This function gets the logs file paths from the directory. Supports rotating files to get the logs by time.

    :param log_files_directory_path: Path to the log files. If specified, the function will get all the files from the
        directory by the 'file_name_pattern'.
    :param log_file_path: Path to the log file. If specified, the function will get the file and all the rotated logs
        associated with this file. The 'file_name_pattern' will become the file name using the file name and extension.

        Example:
        log_file_path = 'C:/logs/test_log.csv'

        # The function will get all the files that start with 'test_log' and have '.csv' extension:
        file_name_pattern = 'test_log*.csv'

        # The 'log_files_directory_path' will also be taken from the 'log_file_path':
        log_files_directory_path = 'C:/logs'
    :param file_name_pattern: Pattern to match the log files names.
        Default file_name_pattern will match all the files.
    :param date_pattern: Pattern to match the date in the log file name.
        If specified, the function will get the log file by the date pattern.
        If not specified, the function will get the file date by file last modified time.
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

    # If log file path is specified, get the file_name_pattern from the file name.
    if log_file_path:
        # Build the file_name_pattern.
        log_file_name: str = Path(log_file_path).stem
        log_file_extension: str = Path(log_file_path).suffix
        file_name_pattern = f'{log_file_name}*{log_file_extension}'

        # Get the directory path from the file path.
        log_files_directory_path = Path(log_file_path).parent

    # Get all the log file paths by the file_name_pattern.
    logs_files: list = filesystem.get_file_paths_from_directory(
        log_files_directory_path,
        file_name_check_pattern=file_name_pattern,
        add_last_modified_time=True,
        sort_by_last_modified_time=True)

    if len(logs_files) > 1:
        if date_pattern:
            latest_timestamp: float = 0
            for file_index, single_file in enumerate(logs_files):
                # Get file name from current loop file path.
                current_file_name: str = Path(single_file['file_path']).name
                # Get the datetime object from the file name by the date pattern.
                try:
                    datetime_object = datetimes.get_datetime_from_complex_string_by_pattern(
                        current_file_name, date_pattern)
                    timestamp_float = datetime_object.timestamp()
                # ValueError will be raised if the date pattern does not match the file name.
                except ValueError:
                    timestamp_float = 0
                # Update the last modified time to the dictionary.
                logs_files[file_index]['last_modified'] = timestamp_float

                if timestamp_float > latest_timestamp:
                    latest_timestamp = timestamp_float

            # Now, there should be a file that doesn't have the string date pattern in the file name.
            # We will add one day to the latest date that we found and assign to that file path.
            for file_index, single_file in enumerate(logs_files):
                if single_file['last_modified'] == 0:
                    latest_timestamp += 86400
                    logs_files[file_index]['last_modified'] = latest_timestamp
                    break

            # Sort the files by the last modified time.
            logs_files = sorted(logs_files, key=lambda x: x['last_modified'], reverse=False)

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
        file_name_pattern: str = '*.*',
        date_pattern: str = None,
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
    :param file_name_pattern: Pattern to match the log files names.
        Default file_name_pattern will match all the files.
    :param date_pattern: Pattern to match the date in the log file name.
        If specified, the function will get the log file by the date pattern.
        If not specified, the function will get the file date by file last modified time.
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

    # Get all the log file paths by the file_name_pattern.
    logs_files: list = get_logs_paths(
        log_files_directory_path=log_files_directory_path,
        log_file_path=log_file_path,
        file_name_pattern=file_name_pattern,
        date_pattern=date_pattern,
        log_type=log_type)

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
                csv_content, header = csvs.read_csv_to_list_of_dicts_by_header(
                    single_file['file_path'], header=header, **print_kwargs)
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


def get_latest_lines(
        log_file_path: str,
        date_pattern: str = None,
        log_type: Literal['csv'] = 'csv',
        get_previous_file: bool = False,
        header: list = None
) -> tuple:
    """
    This function gets the latest lines from the log file.

    :param log_file_path: Path to the log file.
    :param date_pattern: Pattern to match the date in the log file name.
        If specified, the function will get the log file by the date pattern.
        If not specified, the function will get the file date by file last modified time.
    :param log_type: Type of log to get.
    :param get_previous_file: Boolean, if True, the function will get the previous log file.
        For example, your log is set to rotate every Midnight.
        Meaning, once the day will change, the function will get the log file from the previous day in the third entry
        of the return tuple. This happens only once each 24 hours. Not from the time the function was called, but from
        the time the day changed.
    :param header: List of strings that will be the header of the CSV file. Default is 'None'.
        None: the header from the CSV file will be used. The first row of the CSV file will be the header.
            Meaning, that the first line will be skipped and the second line will be the first row of the content.
        List: the list will be used as header.
            All the lines of the CSV file will be considered as content.
    return: List of new lines.

    Usage:
        while True:
            latest_lines, current_lines, existing_lines, last_24_hours_lines = get_latest_log_lines(
                log_file_path='/path/to/log.csv',
                log_type='csv'
            )

            if latest_lines:
                # Do something with the new lines.

            if last_24_hours_lines:
                # Do something with the last 24 hours lines. Reminder, this will happen once a day on log rotation.

            time.sleep(1)
    """

    def extract_new_lines_only(content_lines: list):
        new_lines: list = []
        for row in content_lines:
            # If the row is not in the existing lines, then add it to the new lines.
            if row not in READING_EXISTING_LINES:
                new_lines.append(row)

        if new_lines:
            READING_EXISTING_LINES.extend(new_lines)

        return new_lines

    global EXISTING_LOGS_FILE_COUNT

    # If the existing logs file count is 0, it means that this is the first check. We need to get the current count.
    if EXISTING_LOGS_FILE_COUNT == 0:
        EXISTING_LOGS_FILE_COUNT = len(get_logs_paths(
            log_file_path=log_file_path,
            log_type='csv'
        ))

        # If the count is still 0, then there are no logs to read.
        if EXISTING_LOGS_FILE_COUNT == 0:
            return [], [], header

    if log_type != 'csv':
        raise ValueError('Only "csv" log type is supported.')

    previous_file_lines: list = []

    # Get the latest statistics file path.
    latest_statistics_file_path_object = get_logs_paths(
        log_file_path=log_file_path,
        date_pattern=date_pattern,
        log_type='csv',
        latest_only=True
    )

    latest_statistics_file_path: str = latest_statistics_file_path_object[0]['file_path']

    # Get the previous day statistics file path.
    previous_day_statistics_file_path: Union[str, None] = None
    try:
        previous_day_statistics_file_path = get_logs_paths(
            log_file_path=log_file_path,
            date_pattern=date_pattern,
            log_type='csv',
            previous_day_only=True
        )[0]['file_path']
    except KeyError:
        pass

    # Count all the rotated files.
    current_log_files_count: int = len(get_logs_paths(
        log_file_path=log_file_path,
        log_type='csv'
    ))

    # If the count of the log files is greater than the existing logs file count, it means that the rotation happened.
    # We will read the previous day statistics file.
    new_lines_from_previous_file: list = []
    if current_log_files_count > EXISTING_LOGS_FILE_COUNT:
        current_lines, header = csvs.read_csv_to_list_of_dicts_by_header(
            previous_day_statistics_file_path, header=header, stdout=False)

        if get_previous_file:
            previous_file_lines = current_lines

        EXISTING_LOGS_FILE_COUNT = current_log_files_count

        new_lines_from_previous_file = extract_new_lines_only(current_lines)

        # empty the previous file lines, since the file is rotated.
        READING_EXISTING_LINES.clear()

    current_lines, header = csvs.read_csv_to_list_of_dicts_by_header(
        latest_statistics_file_path, header=header, stdout=False)

    new_lines = extract_new_lines_only(current_lines)

    # If we have new lines from the previous file, we will add the new lines from the latest file.
    if new_lines_from_previous_file:
        new_lines = new_lines_from_previous_file + new_lines

    return new_lines, previous_file_lines, header

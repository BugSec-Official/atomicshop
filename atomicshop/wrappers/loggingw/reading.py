import os
from typing import Literal, Union
from pathlib import Path
import datetime

from ... import filesystem, datetimes
from ...basics import booleans, list_of_classes
from ...file_io import csvs


def get_logs_paths(
        log_file_path: str,
        date_format: str = None,
        latest_only: bool = False,
        previous_day_only: bool = False,
        yesterday_only: bool = False,
        specific_date: str = None
) -> list[filesystem.AtomicPath]:
    """
    This function gets the logs file paths from the directory. Supports rotating files to get the logs by time.

    :param log_file_path: Path to the log file. If specified, the function will get the file and all the rotated logs
        associated with this file. The 'file_name_pattern' will become the file name using the file name and extension.

        Example:
        log_file_path = 'C:/logs/test_log.csv'

        # The function will get all the files that start with 'test_log' and have '.csv' extension:
        file_name_pattern = 'test_log*.csv'

        # The 'log_files_directory_path' will also be taken from the 'log_file_path':
        log_files_directory_path = 'C:/logs'
    :param date_format: date format string pattern to match the date in the log file name.
        If specified, the function will get the log file by the date pattern.
        If not specified, the function will get the file date by file last modified time.

        Example:
        date_format = '%Y-%m-%d'
    :param latest_only: Boolean, if True, only the latest log file path will be returned.
    :param previous_day_only: Boolean, if True, only the log file path from the previous day will be returned.
    :param yesterday_only: Boolean, if True, only the log file path from yesterday will be returned.
        There's a difference between 'previous_day_only' and 'yesterday_only'.
        'previous_day_only' will get the log file from the previous day in the list of files that were found.
        Since that doesn't guarantee that the log file from the previous day is yesterday, we have 'yesterday_only'.
    :param specific_date: Specific date to get the log file path.
        If specified, the function will get the log file by the specific date.
        Meaning that 'date_format' must be specified.
    """

    booleans.is_only_1_true_in_list(
        booleans_list_of_tuples=[
            (latest_only, 'latest_only'),
            (previous_day_only, 'previous_day_only'),
            (yesterday_only, 'yesterday_only'),
            (specific_date, 'specific_date'),
        ],
        raise_if_all_false=False
    )

    if not date_format and specific_date:
        raise ValueError('If "specific_date" is specified, "date_format" must be specified.')

    # Get the file_name_pattern from the file name. Build the file_name_pattern.
    # For some reason if the file name will be '.zip', then the file stem will be '.zip' and the extension will be ''.
    log_file_name: str = Path(log_file_path).stem
    log_file_extension: str = Path(log_file_path).suffix

    if not log_file_extension and '.' in log_file_name:
        log_file_name, log_file_extension = log_file_name.rsplit('.')
        log_file_extension = f'.{log_file_extension}'

    file_name_pattern: str = f'{log_file_name}*{log_file_extension}'

    # Get the directory path from the file path.
    log_files_directory_path: str = str(Path(log_file_path).parent)

    # Get all the log file paths by the file_name_pattern and the date_format string.
    logs_files: list[filesystem.AtomicPath] = filesystem.get_paths_from_directory(
        log_files_directory_path,
        get_file=True,
        file_name_check_pattern=file_name_pattern,
        add_last_modified_time=True,
        sort_by_last_modified_time=True,
        datetime_format=date_format
    )

    # The above will not include the latest log file if it is not rotated yet.
    # noinspection PyTypeChecker
    last_log_file_atomic_path: filesystem.AtomicPath = None
    if os.path.isfile(log_file_path):
        last_log_file_atomic_path = filesystem.AtomicPath(log_file_path)
        last_log_file_atomic_path.update(update_last_modified=True)

    if logs_files and last_log_file_atomic_path and date_format:
        # The problem here is the file name that doesn't contain the date string in the name.
        # If it is regular log rotation, then there will be one file that doesn't have the date string in the name.
        # If the function used to get the previous day log, then there will be no file that doesn't have the date
        # string.

        # Get the latest timestamp from the files with dates.
        latest_datetime_float: float = 0
        for file_index, single_file in enumerate(logs_files):
            if single_file.datetime_float > latest_datetime_float:
                latest_datetime_float = single_file.datetime_float

        # We will add one day to the latest date that we found and assign to the latest file in rotation
        # which is without the datetime string.
        latest_datetime_float += 86400
        last_log_file_atomic_path.datetime_float = latest_datetime_float
        last_log_file_atomic_path.datetime_datetime = datetime.datetime.fromtimestamp(latest_datetime_float)
        last_log_file_atomic_path.datetime_string = (
            last_log_file_atomic_path.datetime_datetime.strftime(date_format))
        last_log_file_atomic_path.datetime_format = date_format

        # Add the last log file to the list.
        logs_files.append(last_log_file_atomic_path)

        # Sort the files by the last modified time.
        logs_files = list_of_classes.sort_by_attributes(logs_files, ['datetime_float'])
    elif last_log_file_atomic_path and logs_files and not date_format:
        logs_files.append(last_log_file_atomic_path)
    elif last_log_file_atomic_path and not logs_files:
        logs_files = [last_log_file_atomic_path]

    if logs_files:
        if latest_only:
            logs_files = [logs_files[-1]]
        elif previous_day_only:
            if len(logs_files) == 1:
                logs_files = []
            else:
                logs_files = [logs_files[-2]]
        elif yesterday_only:
            # Get yesterday's date.
            yesterday_date_string = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime(date_format)
            # Check if there is a yesterday log file.
            logs_files = [single_file
                          for single_file in logs_files if single_file.datetime_string == yesterday_date_string]
        elif specific_date:
            # Check if there is a specific date log file.
            logs_files = [single_file for single_file in logs_files if single_file.datetime_string == specific_date]

    return logs_files


def get_all_log_files_into_list(
        log_file_path: str = None,
        date_format: str = None,
        log_type: Literal['csv'] = 'csv',
        header_type_of_files: Literal['first', 'all'] = 'first',
        remove_logs: bool = False,
        move_to_path: str = None,
        print_kwargs: dict = None
) -> list:
    """
    This function gets the logs contents from the log files. Supports rotating files to get the logs by time.
    All the contents will be merged into one list.

    :param log_file_path: Path to the log file. Check the 'get_logs_paths' function for more details.
    :param date_format: date format string pattern to match the date in the log file name.
        If specified, the function will get the log file by the date pattern.
        If not specified, the function will get the file date by file last modified time.

        Example:
        date_format = '%Y-%m-%d'
    :param log_type: Type of log to get.
    :param header_type_of_files: Type of header to get from the files.
        'first' - Only the first file has a header for CSV. This header will be used for the rest of the files.
        'all' - Each CSV file has a header. Get the header from each file.
    :param remove_logs: Boolean, if True, the logs will be removed after getting them.
    :param move_to_path: Path to move the logs to.
    :param print_kwargs: Keyword arguments dict for 'print_api' function.

    :return: List of dictionaries with the logs content.
    """

    if not print_kwargs:
        print_kwargs = dict()

    if remove_logs and move_to_path:
        raise ValueError('Both "remove_logs" and "move_to_path" cannot be True/specified at the same time.')

    if header_type_of_files not in ['first', 'all']:
        raise ValueError('Only "first" and "all" header types are supported.')

    # Get all the log file paths by the file_name_pattern.
    logs_files: list = get_logs_paths(
        log_file_path=log_file_path,
        date_format=date_format)

    # Read all the logs.
    logs_content: list = list()
    header = None
    for single_file in logs_files:
        if log_type == 'csv':
            if header_type_of_files == 'all':
                csv_content, _ = csvs.read_csv_to_list_of_dicts_by_header(single_file.path, **print_kwargs)
                logs_content.extend(csv_content)
            elif header_type_of_files == 'first':
                # The function gets empty header to read it from the CSV file, the returns the header that it read.
                # Then each time the header is fed once again to the function.
                csv_content, header = csvs.read_csv_to_list_of_dicts_by_header(
                    single_file.path, header=header, **print_kwargs)
                # Any way the first file will be read with header.
                logs_content.extend(csv_content)

                # if not header:
                #     # Get the first line of the file as text, which is the header.
                #     header = csvs.get_header(single_file, **print_kwargs)

    if remove_logs:
        # Remove the statistics files.
        for single_file in logs_files:
            filesystem.remove_file(single_file.path)

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
            filesystem.move_file(single_file.path, move_to_path_with_timestamp)

    return logs_content


class LogReader:
    """
    This class gets the latest lines from the log file.

    return: List of new lines.

    Usage:
        from typing import Union


        # The header of the log file will be read from the first iteration of the log file.
        # When the file is rotated, this header will be used to not read the header again.
        header: Union[list, None] = None
        log_reader = reading.LogReader(
            log_file_path='/path/to/log.csv',
            log_type='csv',
            date_pattern='%Y_%m_%d',
            get_previous_file=True,
            header=header
        )
        while True:
            latest_lines, previous_day_24h_lines, header = log_reader.get_latest_lines(header=header)

            if latest_lines:
                # Do something with the new lines.

            if previous_day_24h_lines:
                # Do something with the last 24 hours lines. Reminder, this will happen once a day on log rotation.

            time.sleep(1)
        """

    def __init__(
            self,
            log_file_path: str,
            date_format: str = None,
            log_type: Literal['csv'] = 'csv',
            get_previous_file: bool = False,
            header: list = None
    ):
        """
        :param log_file_path: Path to the log file.
        :param date_format: date format string pattern to match the date in the log file name.
            If specified, the function will get the log file by the date pattern.
            If not specified, the function will get the file date by file last modified time.

            Example:
            date_format = '%Y-%m-%d'
        :param log_type: Type of log to get.
        :param get_previous_file: Boolean, if True, the function will get the previous log file.
            For example, your log is set to rotate every Midnight.
            Meaning, once the day will change, the function will get the log file from the previous day in the
            third entry of the return tuple. This happens only once each 24 hours. Not from the time
            the function was called, but from the time the day changed.
        :param header: List of strings that will be the header of the CSV file. Default is 'None'.
            None: the header from the CSV file will be used. The first row of the CSV file will be the header.
                Meaning, that the first line will be skipped and the second line will be the first row of the content.
            List: the list will be used as header.
                All the lines of the CSV file will be considered as content.
        """

        self.log_file_path: str = log_file_path
        self.date_format: str = date_format
        self.log_type: Literal['csv'] = log_type
        self.get_previous_file: bool = get_previous_file
        self.header: list = header

        self._reading_existing_lines: list = []
        self._existing_logs_file_count: int = 0

    def _extract_new_lines_only(self, content_lines: list):
        new_lines: list = []
        for row in content_lines:
            # If the row is not in the existing lines, then add it to the new lines.
            if row not in self._reading_existing_lines:
                new_lines.append(row)

        if new_lines:
            self._reading_existing_lines.extend(new_lines)

        return new_lines

    def get_latest_lines(self, header: list = None) -> tuple:
        if header:
            self.header = header

        # If the existing logs file count is 0, it means that this is the first check. We need to get the current count.
        if self._existing_logs_file_count == 0:
            self._existing_logs_file_count = len(get_logs_paths(
                log_file_path=self.log_file_path
            ))

            # If the count is still 0, then there are no logs to read.
            if self._existing_logs_file_count == 0:
                return [], [], self.header

        if self.log_type != 'csv':
            raise ValueError('Only "csv" log type is supported.')

        previous_file_lines: list = []

        # Get the latest statistics file path.
        latest_statistics_file_path_object = get_logs_paths(
            log_file_path=self.log_file_path,
            date_format=self.date_format,
            latest_only=True
        )

        # # If there are no logs to read, return empty lists.
        # if not latest_statistics_file_path_object:
        #     return [], [], self.header

        latest_statistics_file_path: str = latest_statistics_file_path_object[0].path

        # Get the previous day statistics file path.
        previous_day_statistics_file_path: Union[str, None] = None
        try:
            previous_day_statistics_file_path = get_logs_paths(
                log_file_path=self.log_file_path,
                date_format=self.date_format,
                previous_day_only=True
            )[0].path
        # If you get IndexError, it means that there are no previous day logs to read.
        except IndexError:
            pass

        # Count all the rotated files.
        current_log_files_count: int = len(get_logs_paths(
            log_file_path=self.log_file_path
        ))

        # If the count of the log files is greater than the existing logs file count, it means that the rotation
        # happened. We will read the previous day statistics file.
        new_lines_from_previous_file: list = []
        if current_log_files_count > self._existing_logs_file_count:
            current_lines, self.header = csvs.read_csv_to_list_of_dicts_by_header(
                previous_day_statistics_file_path, header=self.header, stdout=False)

            if self.get_previous_file:
                previous_file_lines = current_lines

            self._existing_logs_file_count = current_log_files_count

            new_lines_from_previous_file = self._extract_new_lines_only(current_lines)

            # empty the previous file lines, since the file is rotated.
            self._reading_existing_lines.clear()

        current_lines, self.header = csvs.read_csv_to_list_of_dicts_by_header(
            latest_statistics_file_path, header=self.header, stdout=False)

        new_lines = self._extract_new_lines_only(current_lines)

        # If we have new lines from the previous file, we will add the new lines from the latest file.
        if new_lines_from_previous_file:
            new_lines = new_lines_from_previous_file + new_lines

        return new_lines, previous_file_lines, self.header

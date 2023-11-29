import os
from typing import Literal

from ... import filesystem, datetimes
from ...file_io import csvs


def get_logs(
        path: str,
        pattern: str = '*.*',
        log_type: Literal['csv'] = 'csv',
        header_type_of_files: Literal['first', 'all'] = 'first',
        remove_logs: bool = False,
        move_to_path: str = None,
        print_kwargs: dict = None
):
    """
    This function gets the logs from the log files. Supports rotating files to get the logs by time.

    :param path: Path to the log files.
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

    logs_files: list = filesystem.get_file_paths_from_directory(
        path, file_name_check_pattern=pattern,
        add_last_modified_time=True, sort_by_last_modified_time=True)

    # Read all the logs.
    logs_content: list = list()
    header = None
    for single_file in logs_files:
        if log_type == 'csv':
            if header_type_of_files == 'all':
                csv_content, _ = csvs.read_csv_to_list(single_file['file_path'], **print_kwargs)
                logs_content.extend(csv_content)
            elif header_type_of_files == 'first':
                # The function gets empty header to read it from the CSV file, the returns the header that it read.
                # Then each time the header is fed once again to the function.
                csv_content, header = csvs.read_csv_to_list(single_file['file_path'], header=header, **print_kwargs)
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

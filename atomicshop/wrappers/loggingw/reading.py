from typing import Literal

from ... import filesystem
from ...file_io import csvs, file_io


def get_logs(
        path: str,
        pattern: str = '*.*',
        log_type: Literal['csv'] = 'csv',
        header_type_of_files: Literal['first', 'all'] = 'first',
        remove_logs: bool = False,
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
    :param print_kwargs: Keyword arguments dict for 'print_api' function.
    """

    if not print_kwargs:
        print_kwargs = dict()

    logs_files: list = filesystem.get_files_and_folders(
        path, string_contains=pattern)

    # If there's more than 1 file, it means that the latest file is 'statistics.csv' and it is the first in
    # The found list, so we need to move it to the last place.
    if len(logs_files) > 1:
        logs_files = list(logs_files[1:] + [logs_files[0]])

    # Read all the logs.
    logs_content: list = list()
    header = None
    for single_file in logs_files:
        if log_type == 'csv':
            if header_type_of_files == 'all':
                csv_content, _ = csvs.read_csv_to_list(single_file, **print_kwargs)
                logs_content.extend(csv_content)
            elif header_type_of_files == 'first':
                # The function gets empty header to read it from the CSV file, the returns the header that it read.
                # Then each time the header is fed once again to the function.
                csv_content, header = csvs.read_csv_to_list(single_file, header=header, **print_kwargs)
                # Any way the first file will be read with header.
                logs_content.extend(csv_content)

                # if not header:
                #     # Get the first line of the file as text, which is the header.
                #     header = file_io.read_file(single_file, read_to_list=True, **print_kwargs)[0]
                #     # Split the header to list of keys.
                #     header = header.split(',')

    if remove_logs:
        # Remove the statistics files.
        for single_file in logs_files:
            filesystem.remove_file(single_file)

    return logs_content

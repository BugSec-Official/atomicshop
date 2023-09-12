from typing import Literal

from ... import filesystem
from ...file_io import csvs


def get_logs(
        path: str,
        pattern: str = '*.*',
        log_type: Literal['csv'] = 'csv',
        remove_logs: bool = False,
):
    """
    This function gets the logs from the log files. Supports rotating files to get the logs by time.

    :param path: Path to the log files.
    :param pattern: Pattern to match the log files names.
        Default pattern will match all the files.
    :param log_type: Type of log to get.
    :param remove_logs: Boolean, if True, the logs will be removed after getting them.
    """

    logs_files: list = filesystem.get_files_and_folders(
        path, string_contains=pattern)

    # If there's more than 1 file, it means that the latest file is 'statistics.csv' and it is the first in
    # The found list, so we need to move it to the last place.
    if len(logs_files) > 1:
        logs_files = list(logs_files[1:] + [logs_files[0]])

    # Read all the logs.
    logs_content: list = list()
    for single_file in logs_files:
        if log_type == 'csv':
            logs_content.extend(csvs.read_csv_to_list(single_file))

    if remove_logs:
        # Remove the statistics files.
        for single_file in logs_files:
            filesystem.remove_file(single_file)

    return logs_content

import datetime
import os
import multiprocessing

from ..wrappers.loggingw import reading
from ..archiver import zips
from .. import filesystem


REC_FILE_DATE_TIME_FORMAT: str = "%Y_%m_%d-%H_%M_%S_%f"
REC_FILE_DATE_FORMAT: str = REC_FILE_DATE_TIME_FORMAT.split('-')[0]


def recs_archiver(recs_directory: str) -> list:
    """
    Find recs files in a directory for each day.
    Each day of recordings will have separate archive.

    :param recs_directory: The directory where recordings are stored.
    """

    today_date_string = datetime.datetime.now().strftime(REC_FILE_DATE_FORMAT)

    all_recs_files = reading.get_logs_paths(
        log_files_directory_path=recs_directory,
        file_name_pattern='*.json',
        date_format=REC_FILE_DATE_FORMAT
    )

    archive_directories: list = list()
    for recs_file_dict in all_recs_files:
        # We don't need to archive today's files.
        if today_date_string == recs_file_dict['date_string']:
            continue

        target_directory_path: str = f"{recs_directory}{os.sep}{recs_file_dict['date_string']}"
        if target_directory_path not in archive_directories:
            archive_directories.append(target_directory_path)

        filesystem.create_directory(target_directory_path)
        filesystem.move_file(
            recs_file_dict['file_path'], f'{target_directory_path}{os.sep}{recs_file_dict["file_name"]}')

    # Archive directories.
    archived_files: list = list()
    for archive_directory in archive_directories:
        archived_file: str = zips.archive_directory(
            archive_directory, remove_original=True, include_root_directory=True)
        archived_files.append(archived_file)

    return archived_files


def recs_archiver_in_process(recs_directory: str):
    """
    Archive recs files in a directory for each day in a separate process.
    """

    process = multiprocessing.Process(target=recs_archiver, args=(recs_directory,))
    process.start()

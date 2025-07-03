import datetime
import os
import multiprocessing
import logging

from ..archiver import zips
from .. import filesystem, print_api
from .. wrappers.loggingw import consts, loggingw


REC_FILE_DATE_TIME_MILLISECONDS_FORMAT: str = f'{consts.DEFAULT_ROTATING_SUFFIXES_FROM_WHEN["S"]}_%f'
REC_FILE_DATE_TIME_FORMAT: str = f'{consts.DEFAULT_ROTATING_SUFFIXES_FROM_WHEN["S"]}'
REC_FILE_DATE_FORMAT: str = REC_FILE_DATE_TIME_FORMAT.split('_')[0]


def recs_archiver(
        recs_directory: str,
        logging_queue: multiprocessing.Queue,
        logger_name: str,
        finalize_output_queue: multiprocessing.Queue
) -> list | None:
    """
    Find recs files in a directory for each day.
    Each day of recordings will have separate archive.

    :param recs_directory: The directory where recordings are stored.
    :param logging_queue: The queue for logging messages.
    :param logger_name: The name of the logger to use for logging.
        This is the base name that '.rec_packer' will be added to it.
    :param finalize_output_queue: output queue for results/exceptions.
    """

    logger_name = f"{logger_name}.rec_packer"

    rec_packer_logger_with_queue_handler: logging.Logger = loggingw.create_logger(
        logger_name=logger_name,
        add_queue_handler=True,
        log_queue=logging_queue)

    print_api.print_api(
        'Starting recs archiver process.', color='blue',
        logger=rec_packer_logger_with_queue_handler
    )

    today_date_string = datetime.datetime.now().strftime(REC_FILE_DATE_FORMAT)

    # There should not be recording json files in recs root.
    files_in_recs_root: list = filesystem.get_paths_from_directory(
        recs_directory, get_file=True, file_name_check_pattern='*\\.json', recursive=False)
    if files_in_recs_root:
        raise NotImplementedError("The files in recs root directory are not implemented yet.")

    # Each engine should have its own directory inside recordings. We will find all the directories inside recs folder.
    directory_paths_in_recs: list = filesystem.get_paths_from_directory(
        recs_directory, get_directory=True, recursive=False)

    file_list_per_directory: list = list()
    for directory_path in directory_paths_in_recs:
        all_recs_files = filesystem.get_paths_from_directory(
            directory_path=directory_path.path,
            get_file=True,
            file_name_check_pattern='*.json',
            datetime_format=REC_FILE_DATE_FORMAT,
            recursive=False
        )
        file_list_per_directory.append((directory_path, all_recs_files))


    try:
        archived_files: list = list()
        for directory_path, all_recs_files in file_list_per_directory:
            for recs_atomic_path in all_recs_files:
                # We don't need to archive today's files.
                if today_date_string == recs_atomic_path.datetime_string:
                    continue

                target_directory_path: str = f"{directory_path.path}{os.sep}{recs_atomic_path.datetime_string}"
                filesystem.create_directory(target_directory_path)
                filesystem.move_file(
                    recs_atomic_path.path, target_directory_path)

            # Archive directories.
            archive_directories: list = filesystem.get_paths_from_directory(
                directory_path.path, get_directory=True, recursive=False)
            for archive_directory in archive_directories:
                archived_file: str = zips.archive_directory(
                    archive_directory.path, remove_original=True, include_root_directory=True)
                archived_files.append(archived_file)

        finalize_output_queue.put(None)

        print_api.print_api(
            'Finished recs archiver process.', color='blue',
            logger=rec_packer_logger_with_queue_handler
        )

        return archived_files
    except Exception as e:
        print_api.print_api(
            f"Error while archiving recs files: {e}",
            color='red',
            logger=rec_packer_logger_with_queue_handler
        )

        finalize_output_queue.put(e)
        return None


def recs_archiver_in_process(
        recs_directory: str,
        logging_queue: multiprocessing.Queue,
        logger_name: str,
        finalize_output_queue: multiprocessing.Queue
) -> multiprocessing.Process:
    """
    Archive recs files in a directory for each day in a separate process.

    :param recs_directory: The directory where recordings are stored.
    :param logging_queue: The queue for logging messages.
    :param logger_name: The name of the logger to use for logging.
    :param finalize_output_queue: output queue for results/exceptions.
    """

    process = multiprocessing.Process(
        target=recs_archiver, args=(recs_directory, logging_queue, logger_name, finalize_output_queue))
    process.start()
    return process

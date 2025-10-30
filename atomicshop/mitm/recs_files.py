import datetime
import os
import multiprocessing
import logging
import zipfile
import shutil

from .. import filesystem, print_api
from .. wrappers.loggingw import consts, loggingw


REC_FILE_DATE_TIME_MILLISECONDS_FORMAT: str = f'{consts.DEFAULT_ROTATING_SUFFIXES_FROM_WHEN["S"]}_%f'
REC_FILE_DATE_TIME_FORMAT: str = f'{consts.DEFAULT_ROTATING_SUFFIXES_FROM_WHEN["S"]}'
REC_FILE_DATE_FORMAT: str = REC_FILE_DATE_TIME_FORMAT.split('_')[0]


def archive(
        directory_path: str,
        include_root_directory: bool = True,
) -> str:
    """
    Function archives the directory.
    :param directory_path: string, full path to the directory.
    :param include_root_directory: boolean, default is 'True'.
        'True': The root directory will be included in the archive.
        'False': The root directory will not be included in the archive.
        True is usually the case in most archiving utilities.
    :return: string, full path to the archived file.
    """

    # This is commonly used and supported by most ZIP utilities.
    compression_method = zipfile.ZIP_DEFLATED

    archive_path: str = directory_path + '.zip'
    with zipfile.ZipFile(archive_path, 'w', compression_method) as zip_object:
        for root, _, files in os.walk(directory_path):
            for file in files:
                file_path = os.path.join(root, file)

                # If including the root directory, use the relative path from the parent directory of the root
                if include_root_directory:
                    arcname = os.path.relpath(file_path, os.path.dirname(directory_path))
                else:
                    arcname = os.path.relpath(file_path, directory_path)

                zip_object.write(file_path, arcname)

    return archive_path


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
            print_api.print_api(f"Archiving recs files in directory: {directory_path.path}",
                      logger=rec_packer_logger_with_queue_handler, color='blue')
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

            if not archive_directories:
                print_api.print_api(
                    f"No directories to archive in: {directory_path.path}",
                    color='blue',
                    logger=rec_packer_logger_with_queue_handler
                )
            else:
                total_archived_files: int = 0
                for archive_directory in archive_directories:
                    files_to_archive: list = filesystem.get_paths_from_directory(
                        directory_path=archive_directory.path, get_file=True, recursive=False)
                    total_archived_files += len(files_to_archive)
                    archived_file: str = archive(archive_directory.path, include_root_directory=True)
                    # Remove the original directory after archiving.
                    shutil.rmtree(archive_directory.path, ignore_errors=True)
                    archived_files.append(archived_file)

                print_api.print_api(
                    f'Archived: 'f'Directories: {len(archive_directories)} | '
                    f'Total Files: {total_archived_files} | In: {directory_path.path}',
                    logger=rec_packer_logger_with_queue_handler, color='blue')
                print_api.print_api(f'Archived files: {archived_files}', logger=rec_packer_logger_with_queue_handler)

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

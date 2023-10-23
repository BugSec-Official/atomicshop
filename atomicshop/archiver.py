import os
import time
import shutil
import zipfile

from .print_api import print_api
from . import filesystem


def extract_archive_with_shutil(file_path: str, target_directory: str, **kwargs) -> str:
    """
    Function extracts the archive to target directory.
    Returns full path to extracted directory.
    This function doesn't preserve the original date and time of files from the archive, instead the time of extraction
    will be applied.

    :param file_path: Full file path to archived file to extract.
    :param target_directory: The directory on the filesystem to extract the file to.
    :return: str.
    """

    print_api(f'Extracting {file_path}', **kwargs)

    extracted_directory: str = str()

    try:
        shutil.unpack_archive(file_path, target_directory)
        file_name = file_path.rsplit(os.sep, maxsplit=1)[1]
        file_name_no_extension = file_name.rsplit('.', maxsplit=1)[0]
        extracted_directory: str = target_directory + os.sep + file_name_no_extension
    except Exception as exception_object:
        print_api(f'Error extracting: {file_path}', error_type=True, **kwargs)
        print_api(exception_object, error_type=True, **kwargs)
        pass

    print_api(f'Extracted to: {extracted_directory}', **kwargs)
    return extracted_directory


def extract_archive_with_zipfile(
        archive_path: str,
        extract_directory: str = None,
        files_without_directories: bool = False,
        remove_first_directory: bool = False,
        print_kwargs: dict = None
) -> str:
    """
    Function will extract the archive using standard library 'zipfile'.
    This method preserves original date and time of the files inside the archive.

    :param archive_path: string, full path to archived file.
    :param extract_directory: string, full path to directory that the files will be extracted to.
        If not specified, the files will be extracted to the same directory as the archived file, using the file name
        without extension as the directory name.
    :param files_without_directories: boolean, default 'False'.
        'True': All the files in the archive will be extracted without subdirectories hierarchy.
            Meaning, that if there are duplicate file names, the latest file with the same file name will overwrite
            all the rest of the files with the same name.
        'False': Subdirectory hierarchy will be preserved as it is currently in the archived file.
    :param remove_first_directory: boolean, default is 'False'.
        'True': all the files will be extracted without first directory in the hierarchy.
            Example: package_some_name_1.1.1_build/subdir1/file.exe
            Will be extracted as: subdir/file.exe
    :param print_kwargs: dict, kwargs for print_api.

    :return: string, full path to directory that the files were extracted to.
    """

    if print_kwargs is None:
        print_kwargs = dict()

    # If 'extract_directory' is not specified, extract to the same directory as the archived file.
    if extract_directory is None:
        extract_directory = (
                filesystem.get_file_directory(archive_path) + os.sep +
                filesystem.get_file_name_without_extension(archive_path))

    print_api(f'Extracting to directory: {extract_directory}', **print_kwargs)

    # initiating the archived file path as 'zipfile.ZipFile' object.
    with zipfile.ZipFile(archive_path) as zip_object:
        # '.infolist()' method of the object contains all the directories and files that are in the archive including
        # information about each one, like date and time of archiving.
        for zip_info in zip_object.infolist():
            # '.filename' attribute of the 'infolist()' method is relative path to each directory and file.
            # If 'filename' ends with '/' it is a directory (it doesn't matter if it is windows or *nix)
            # If so, skip current iteration.
            if zip_info.filename[-1] == '/':
                continue

            if files_without_directories:
                # Put into 'filename' the string that contains only the filename without subdirectories.
                zip_info.filename = os.path.basename(zip_info.filename)
            elif remove_first_directory:
                # Cut the first directory from the filename.
                zip_info.filename = zip_info.filename.split('/', maxsplit=1)[1]

            print_api(f'Extracting: {zip_info.filename}', **print_kwargs)

            # Extract current file from the archive using 'zip_info' of the current file with 'filename' that we
            # updated under specified parameters to specified directory.
            zip_object.extract(zip_info, extract_directory)

            # === Change the date and time of extracted file from current time to the time specified in 'zip_info'.
            # Get full path to extracted file.
            extracted_file_path: str = extract_directory + os.sep + zip_info.filename
            # Create needed datetime object with original archived datetime from 'zip_info.date_time'.
            date_time = time.mktime(zip_info.date_time + (0, 0, -1))
            # Using 'os' library, changed the datetime of the file to the object created in previous step.
            os.utime(extracted_file_path, (date_time, date_time))
    print_api('Extraction done.', color="green", **print_kwargs)

    return extract_directory

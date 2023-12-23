import os
import shutil

from ..print_api import print_api


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

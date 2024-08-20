import os
import time
import zipfile
from io import BytesIO
from typing import Union, Literal

from .. import filesystem
from ..print_api import print_api


def is_zip_zipfile(file_object: Union[str, bytes]) -> bool:
    """
    Function checks if the file is a zip file.
    :param file_object: can be two types:
        string, full path to the file.
        bytes or BytesIO, the bytes of the file.
    :return: boolean.
    """

    try:
        if isinstance(file_object, bytes):
            with BytesIO(file_object) as file_object:
                with zipfile.ZipFile(file_object) as zip_object:
                    zip_object.testzip()
                    return True
        elif isinstance(file_object, str):
            with zipfile.ZipFile(file_object) as zip_object:
                zip_object.testzip()
                return True
    except zipfile.BadZipFile:
        return False


def is_zip_magic_number(file_path: str) -> bool:
    """
    Function checks if the file is a zip file using magic number.
    :param file_path: string, full path to the file.
    :return: boolean.

    50 4B 03 04: This is the most common signature, found at the beginning of a ZIP file.
        It signifies the start of a file within the ZIP archive and is present in almost all ZIP files.
        Each file within the ZIP archive starts with this signature.
    50 4B 05 06: This is the end of central directory record signature.
        It's found at the end of a ZIP file and is essential for identifying the structure of the ZIP archive,
        especially in cases where the file is split or is a multi-part archive.
    50 4B 07 08: This signature is used for spanned ZIP archives (also known as split or multi-volume ZIP archives).
        It's found in the end of central directory locator for ZIP files that are split across multiple volumes.
    """

    with open(file_path, 'rb') as file:
        # Read the first 4 bytes of the file
        signature = file.read(4)

    # Check if the signature matches any of the ZIP signatures
    return signature in [b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08']


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


def get_file_list_from_zip(file_path: str) -> list:
    """
    Function returns the list of file names and their relative directories inside the zip file.
    :param file_path: string, full path to the zip file.
    :return: list of strings.
    """

    with zipfile.ZipFile(file_path, 'r') as zip_object:
        return zip_object.namelist()


def archive_directory(
        directory_path: str,
        compression: Literal[
            'store',
            'deflate',
            'bzip2',
            'lzma'] = 'deflate',
        include_root_directory: bool = True,
        remove_original: bool = False
) -> str:
    """
    Function archives the directory.
    :param directory_path: string, full path to the directory.
    :param compression: string, default is 'deflate'.
        'store': No compression.
        'deflate': Standard ZIP compression.
        'bzip2': BZIP2 compression.
            Provides better compression than Deflate but is typically slower. This method might not be supported by
            all ZIP utilities.
        'lzma': LZMA compression.
            high compression ratios but is also slower compared to Deflate. This method is less commonly used and
            may not be supported by all ZIP utilities.
    :param include_root_directory: boolean, default is 'True'.
        'True': The root directory will be included in the archive.
        'False': The root directory will not be included in the archive.
        True is usually the case in most archiving utilities.
    :param remove_original: boolean, default is 'False'. If 'True', the original directory will be removed.
    :return: string, full path to the archived file.
    """

    if compression == 'store':
        compression_method = zipfile.ZIP_STORED
    elif compression == 'deflate':
        compression_method = zipfile.ZIP_DEFLATED
    elif compression == 'bzip2':
        compression_method = zipfile.ZIP_BZIP2
    elif compression == 'lzma':
        compression_method = zipfile.ZIP_LZMA
    else:
        raise ValueError(f"Unsupported compression method: {compression}")

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

    if remove_original:
        filesystem.remove_directory(directory_path)

    return archive_path


# def search_file_in_zip(
#         file_path: str = None,
#         file_bytes: bytes = None,
#         file_names_to_search: list[str] = None,
#         case_sensitive: bool = True,
#         return_first_only: bool = False,
#         return_empty_list_per_file_name: bool = False,
#         recursive: bool = False,
#         callback_functions: list = None,
#         extract_file_to_path: str = None
# ) -> dict[str, list[bytes]]:
#     """
#     Function searches for the file names inside the zip file and returns a dictionary where the keys are the
#     names of the callback functions and the values are lists of found file bytes.
#     :param file_path: string, full path to the zip file.
#     :param file_bytes: bytes, the bytes of the zip file.
#     :param file_names_to_search: list of strings, the names of the files to search.
#     :param case_sensitive: boolean, default is 'True'. Determines if file name search should be case sensitive.
#     :param return_first_only: boolean, default is 'False'. Return only the first found file for each file name.
#     :param return_empty_list_per_file_name: boolean, default is 'False'.
#         True: Return empty list for each file name that wasn't found.
#         False: Don't return empty list for each file name that wasn't found.
#     :param recursive: boolean, default is 'False'. If True, search for file names recursively in nested zip files.
#     :param callback_functions: list of callables, default is None. Each function takes a file name and should return a
#         boolean that will tell the main function if this file is 'found' or not.
#     :param extract_file_to_path: string, full path to the directory where the found files should be extracted.
#     :return: dictionary of lists of bytes.
#     """
#
#     def get_unique_filename(directory, filename):
#         """
#         Generates a unique filename by appending a number if the file already exists.
#         """
#         name, ext = os.path.splitext(filename)
#         counter = 1
#         unique_filename = filename
#         while os.path.exists(os.path.join(directory, unique_filename)):
#             unique_filename = f"{name}_{counter}{ext}"
#             counter += 1
#         return unique_filename
#
#     def is_zip_file(file, zip_obj):
#         try:
#             with zip_obj.open(file) as file_data:
#                 with zipfile.ZipFile(BytesIO(file_data.read())) as zip_file:
#                     if zip_file.testzip() is None:  # No errors found
#                         return True
#         except zipfile.BadZipFile:
#             return False
#         return False
#
#     def match_file_name(target, current):
#         if case_sensitive:
#             return current.endswith(target)
#         else:
#             return current.lower().endswith(target.lower())
#
#     def search_in_zip(zip_obj, file_names, results, found_set):
#         for item in zip_obj.infolist():
#             if item.filename.endswith('/'):  # Skip directories
#                 continue
#             is_nested_zip = recursive and is_zip_file(item.filename, zip_obj)
#
#             with zip_obj.open(item) as file_data:
#                 archived_file_bytes = file_data.read()
#
#                 # This is needed to know if the file should be extracted to directory or not.
#                 should_extract = False
#
#                 name_matched = False
#                 if file_names is not None:
#                     name_matched = any(match_file_name(file_name, item.filename) for file_name in file_names)
#                     if name_matched:
#                         should_extract = True
#
#                 callback_matched = False
#                 if callback_functions:
#                     for callback in callback_functions:
#                         callback_result = callback(archived_file_bytes)
#                         if callback_result:
#                             callback_matched = True
#                             # Initialize key for callback function name if not present
#                             if callback.__name__ not in results:
#                                 results[callback.__name__] = []
#                             file_info = {
#                                 'bytes': archived_file_bytes,
#                                 'name': item.filename,
#                                 'size': item.file_size,
#                                 'modified_time': item.date_time
#                             }
#                             results[callback.__name__].append(file_info)
#                             if return_first_only:
#                                 found_set.add(item.filename)
#
#                             should_extract = True
#                             break  # Stop checking other callbacks if one has found it
#
#                 if should_extract and extract_file_to_path:
#                     unique_filename = get_unique_filename(extract_file_to_path, os.path.basename(item.filename))
#                     with open(os.path.join(extract_file_to_path, unique_filename), 'wb') as f:
#                         f.write(archived_file_bytes)
#
#                 if not callback_matched:
#                     if is_nested_zip:
#                         # If the file is a nested ZIP and hasn't matched a callback, search recursively
#                         nested_zip_bytes = BytesIO(archived_file_bytes)
#                         with zipfile.ZipFile(nested_zip_bytes) as nested_zip:
#                             search_in_zip(nested_zip, file_names, results, found_set)
#                     elif name_matched:
#                         # Handle name match when no callbacks are provided or no callback matched
#                         if item.filename not in results:
#                             results[item.filename] = []
#                         file_info = {
#                             'bytes': archived_file_bytes,
#                             'name': item.filename,
#                             'size': item.file_size,
#                             'modified_time': item.date_time
#                         }
#                         results[item.filename].append(file_info)
#                         if return_first_only:
#                             found_set.add(item.filename)  # Mark as found
#
#                 if file_names is not None and len(found_set) == len(file_names):
#                     return  # All files found, stop searching
#
#     if file_names_to_search is None and callback_functions is None:
#         raise ValueError("Either file_names_to_search or callback_functions must be provided.")
#
#     # Initialize results dictionary.
#     if callback_functions:
#         results = {callback.__name__: [] for callback in callback_functions}
#     else:
#         results = {}
#
#     found_set = set()
#     if file_bytes is not None:
#         with zipfile.ZipFile(BytesIO(file_bytes), 'r') as zip_ref:
#             search_in_zip(zip_ref, file_names_to_search, results, found_set)
#     elif file_path is not None:
#         with zipfile.ZipFile(file_path, 'r') as zip_ref:
#             search_in_zip(zip_ref, file_names_to_search, results, found_set)
#     else:
#         raise ValueError("Either file_path or file_bytes must be provided.")
#
#     if not return_empty_list_per_file_name:
#         # Filter out keys with empty lists
#         results = {key: value for key, value in results.items() if value}
#
#     return results

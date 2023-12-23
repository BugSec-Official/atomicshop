import os
import zipfile
from io import BytesIO

from . import zip, sevenz

import py7zr


def _get_unique_filename(directory, filename):
    """
    Generates a unique filename by appending a number if the file already exists.
    """
    name, ext = os.path.splitext(filename)
    counter = 1
    unique_filename = filename
    while os.path.exists(os.path.join(directory, unique_filename)):
        unique_filename = f"{name}_{counter}{ext}"
        counter += 1
    return unique_filename


def _is_zip_file(file, zip_obj):
    try:
        with zip_obj.open(file) as file_data:
            with zipfile.ZipFile(BytesIO(file_data.read())) as zip_file:
                if zip_file.testzip() is None:  # No errors found
                    return True
    except zipfile.BadZipFile:
        return False
    return False


def _match_file_name(target, current, case_sensitive):
    if case_sensitive:
        return current.endswith(target)
    else:
        return current.lower().endswith(target.lower())


def _handle_nested_zip(
        zip_obj, item, archived_file_bytes, file_names, results, found_set, recursive, return_first_only,
        case_sensitive, callback_functions, extract_file_to_path):

    if recursive and _is_zip_file(item.filename, zip_obj):
        nested_zip_bytes = BytesIO(archived_file_bytes)
        with zipfile.ZipFile(nested_zip_bytes) as nested_zip:
            _search_in_archive(
                nested_zip, file_names, results, found_set, case_sensitive, return_first_only, recursive,
                callback_functions, extract_file_to_path)


def _handle_file_extraction(item, extract_file_to_path, archived_file_bytes):
    if extract_file_to_path:
        unique_filename = _get_unique_filename(extract_file_to_path, os.path.basename(item.filename))
        with open(os.path.join(extract_file_to_path, unique_filename), 'wb') as f:
            f.write(archived_file_bytes)


def _handle_callback_matching(
        item, archive_type, archived_file_bytes, callback_functions, results, found_set, return_first_only):

    for callback in callback_functions:
        callback_result = callback(archived_file_bytes)
        if callback_result:
            # Initialize key for callback function name if not present
            if callback.__name__ not in results:
                results[callback.__name__] = []

            if archive_type == 'zip':
                file_info = {
                    'bytes': archived_file_bytes,
                    'name': item.filename,
                    'size': item.file_size,
                    'modified_time': item.date_time
                }
            elif archive_type == '7z':
                file_info = {
                    'bytes': archived_file_bytes,
                    'name': item.filename,
                    'size': item.uncompressed,
                    'modified_time': item.creationtime
                }
            results[callback.__name__].append(file_info)
            if return_first_only:
                found_set.add(item.filename)
            return True
    return False


def _handle_name_matching(item, archived_file_bytes, file_names, case_sensitive, results, found_set, return_first_only):
    if any(_match_file_name(file_name, item.filename, case_sensitive) for file_name in file_names):
        if item.filename not in results:
            results[item.filename] = []
        file_info = {
            'bytes': archived_file_bytes,
            'name': item.filename,
            'size': item.file_size,
            'modified_time': item.date_time
        }
        results[item.filename].append(file_info)
        if return_first_only:
            found_set.add(item.filename)


def _search_in_archive(
        arch_obj, archive_type, file_names, results, found_set, case_sensitive, return_first_only, recursive,
        callback_functions, extract_file_to_path):

    file_info_list = None
    if archive_type == 'zip':
        file_info_list = arch_obj.infolist()
    elif archive_type == '7z':
        file_info_list = arch_obj.list()

    for item in file_info_list:
        if item.filename.endswith('/'):  # Skip directories
            continue

        archived_file_bytes = None
        if archive_type == 'zip':
            with arch_obj.open(item) as file_data:
                archived_file_bytes = file_data.read()
        elif archive_type == '7z':
            file_dict = arch_obj.read(item.filename)
            archived_file_bytes = file_dict[item.filename].read()

        callback_matched = False
        if callback_functions:
            callback_matched = _handle_callback_matching(
                item, archive_type, archived_file_bytes, callback_functions, results, found_set, return_first_only)

        if callback_matched:
            _handle_file_extraction(item, extract_file_to_path, archived_file_bytes)
        else:
            _handle_nested_zip(
                arch_obj, item, archived_file_bytes, file_names, results, found_set, recursive, return_first_only,
                case_sensitive, callback_functions, extract_file_to_path)
            if file_names and not callback_matched:
                _handle_name_matching(
                    item, archived_file_bytes, file_names, case_sensitive, results, found_set, return_first_only)

        if file_names is not None and len(found_set) == len(file_names):
            break  # All files found, stop searching


def _initialize_results(callback_functions):
    if callback_functions:
        return {callback.__name__: [] for callback in callback_functions}
    else:
        return {}


def _open_archive(archive_type, file_like_object):
    if archive_type == 'zip':
        return zipfile.ZipFile(file_like_object, 'r')
    elif archive_type == '7z':
        return py7zr.SevenZipFile(file_like_object, 'r')
    else:
        raise ValueError("Unsupported archive format.")


def _get_archive_type(file_path, file_bytes) -> tuple:
    if file_bytes is not None:
        file_like_object = BytesIO(file_bytes)
    elif file_path is not None:
        file_like_object = file_path
    else:
        raise ValueError("Either file_path or file_bytes must be provided.")

    if zip.is_zip_zipfile(file_path=file_like_object):
        return 'zip', file_like_object
    elif sevenz.is_7z(file_path=file_like_object):
        return '7z', file_like_object
    else:
        raise ValueError("Unsupported archive format.")


def _search_archive_content(
        file_path, file_bytes, file_names_to_search, results, found_set, case_sensitive, return_first_only, recursive,
        callback_functions, extract_file_to_path):

    archive_type, file_like_object = _get_archive_type(file_path, file_bytes)

    with _open_archive(archive_type, file_like_object) as archive_ref:
        _search_in_archive(archive_ref, archive_type, file_names_to_search, results, found_set, case_sensitive, return_first_only,
                           recursive, callback_functions, extract_file_to_path)


def search_file_in_archive(
        file_path: str = None,
        file_bytes: bytes = None,
        file_names_to_search: list[str] = None,
        case_sensitive: bool = True,
        return_first_only: bool = False,
        return_empty_list_per_file_name: bool = False,
        recursive: bool = False,
        callback_functions: list = None,
        extract_file_to_path: str = None
) -> dict[str, list[bytes]]:
    """
    Function searches for the file names inside the zip file and returns a dictionary where the keys are the
    names of the callback functions and the values are lists of found file bytes.
    :param file_path: string, full path to the zip file.
    :param file_bytes: bytes, the bytes of the zip file.
    :param file_names_to_search: list of strings, the names of the files to search.
    :param case_sensitive: boolean, default is 'True'. Determines if file name search should be case sensitive.
    :param return_first_only: boolean, default is 'False'. Return only the first found file for each file name.
    :param return_empty_list_per_file_name: boolean, default is 'False'.
        True: Return empty list for each file name that wasn't found.
        False: Don't return empty list for each file name that wasn't found.
    :param recursive: boolean, default is 'False'. If True, search for file names recursively in nested zip files.
    :param callback_functions: list of callables, default is None. Each function takes a file name and should return a
        boolean that will tell the main function if this file is 'found' or not.
    :param extract_file_to_path: string, full path to the directory where the found files should be extracted.
    :return: dictionary of lists of bytes.
    """

    if file_names_to_search is None and callback_functions is None:
        raise ValueError("Either file_names_to_search or callback_functions must be provided.")

    # Initialize results dictionary.
    results = _initialize_results(callback_functions)
    found_set = set()

    _search_archive_content(
        file_path, file_bytes, file_names_to_search, results, found_set, case_sensitive, return_first_only, recursive,
        callback_functions, extract_file_to_path)

    if not return_empty_list_per_file_name:
        # Filter out keys with empty lists.
        results = {key: value for key, value in results.items() if value}

    return results

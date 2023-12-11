from .wrappers import astw
from .basics import enumerations
from .file_io import file_io
from . import hashing


def find_and_replace_in_file(
        file_path: str,
        find_and_replace_list: list[tuple[str, str, str, str]],
        encoding: str = None,
        raise_if_more_than_one_string_found: bool = False,
        raise_if_more_than_one_class_or_function_found: bool = False,
        file_sha256: str = None
) -> None:
    """
    Find and replace string in file.

    :param file_path: String with full file path to read.
    :param find_and_replace_list: list of tuples. Each tuple has 4 strings.
        1: Class name, if the string to replace is not in a class, put 'None'.
        2: Function name, if the string to replace is not in a function, put 'None'.
            Also, if Class name and Function Name are both 'None', then it will search for the string in the whole file.
        3: String to find.
        4: String to replace to.
    :param encoding: string, read the file with encoding. Example: 'utf-8'. 'None' is default, since it is default
        in 'open()' function.
    :param raise_if_more_than_one_string_found: Boolean, if True, the function will raise an error if more than one
        string instance was found per entry in the 'find_and_replace_list'.
    :param raise_if_more_than_one_class_or_function_found: Boolean, if True, the function will raise an error if more
        than one class or function was found per entry in the 'find_and_replace_list'.
    :param file_sha256: string, if specified, will check the file's SHA256 hash is the same as specified
        before any changes. If it is not the same - will raise an error.
    :return: None
    """

    if file_sha256 is not None:
        file_hash: str = hashing.hash_file(file_path)
        if file_hash != file_sha256:
            raise ResourceWarning(
                f"File's SHA256 hash is not the same as specified. Nothing was changed.\n"
                f"File path: {file_path}\n"
                f"File SHA256 hash: {file_hash}\n"
                f"Specified SHA256 hash: {file_sha256}")

    # Read the file to variable.
    file_data = file_io.read_file(file_path=file_path, read_to_list=True, encoding=encoding)

    # Initialize the cache dictionary
    block_lines_cache: dict = {}

    for single_find_replace in find_and_replace_list:
        find_class_name: str = single_find_replace[0]
        find_function_name: str = single_find_replace[1]
        find_what_string: str = single_find_replace[2]
        replace_to: str = single_find_replace[3]

        # list_of_blocks: list[tuple[int, int]] = list()
        cache_key = (find_class_name, find_function_name)
        if cache_key in block_lines_cache:
            # Retrieve from cache
            list_of_blocks = block_lines_cache[cache_key]
        else:
            # Use AST to find the start and end lines of the class or function.
            if find_class_name is not None or find_function_name is not None:
                list_of_blocks = astw.find_code_block(
                    file_path, class_name=find_class_name, function_name=find_function_name)
                if raise_if_more_than_one_class_or_function_found and len(list_of_blocks) > 1:
                    raise LookupError(f"More than one class or function was found in the file: {file_path}\n"
                                      f"Nothing was changed.")
            else:
                list_of_blocks = [(1, len(file_data))]

            # Cache the result
            block_lines_cache[cache_key] = list_of_blocks

        for start_line, end_line in list_of_blocks:
            # Adjust line numbers for zero-based index.
            start_line -= 1
            end_line -= 1

            # Find the string.
            found_string_indexes: list = list()
            # for string_index, line in enumerate(file_data, start=start_line):
            for string_index, line in enumerations.enumerate_from_start_to_end_index(file_data, start_line, end_line):
                if find_what_string in line:
                    found_string_indexes.append(string_index)

                    if raise_if_more_than_one_string_found and len(found_string_indexes) > 1:
                        raise LookupError(f"More than one string instance was found in the file: {file_path}\n"
                                          f"Nothing was changed.")

            if not found_string_indexes:
                raise LookupError(f"String was not found in the file: {file_path}\n"
                                  f"Between lines: {start_line + 1} and {end_line + 1}\n"
                                  f"Nothing was changed.")

            # Replace the string.
            for index in found_string_indexes:
                file_data[index] = file_data[index].replace(find_what_string, replace_to)

    file_io.write_file(content=file_data, file_path=file_path, encoding=encoding, convert_list_to_string=True)

from .wrappers import astw
from .basics import enumerations
from .file_io import file_io
from . import hashing


class FindAndReplaceInfo:
    """
    This class is used to store information about the find and replace operation.
    """
    def __init__(
            self,
            find_what: str,
            replace_to: str,
            class_name: str = None,
            function_name: str = None,
    ):
        """
        :param find_what: string to find.
        :param replace_to: string, replace to this string.
        :param class_name: string name of the class to search in,
            if the string to replace is not in a class, put 'None'.
        :param function_name: string of the function name to search in,
            if the string to replace is not in a function, put 'None'.
            Also, if Class name and Function Name are both 'None', then it will search for the string in the whole file.
        """
        self.find_what: str = find_what
        self.replace_to: str = replace_to
        self.class_name: str = class_name
        self.function_name: str = function_name


def find_and_replace_in_file(
        file_path: str,
        find_and_replace_list: list[FindAndReplaceInfo],
        encoding: str = None,
        raise_if_more_than_one_string_found: bool = False,
        raise_if_more_than_one_class_or_function_found: bool = False,
        file_sha256: str = None
) -> None:
    """
    Find and replace string in file.

    :param file_path: String with full file path to read.
    :param find_and_replace_list: list of FindAndReplaceInfo instances.
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
        if file_hash.lower() != file_sha256.lower():
            raise ResourceWarning(
                f"File's SHA256 hash is not the same as specified. Nothing was changed.\n"
                f"File path: {file_path}\n"
                f"File SHA256 hash: {file_hash}\n"
                f"Specified SHA256 hash: {file_sha256}")

    # Read the file to variable.
    file_data = file_io.read_file(file_path=file_path, read_to_list=True, encoding=encoding)

    # Initialize the cache dictionary
    block_lines_cache: dict = {}

    for single_find in find_and_replace_list:
        cache_key = (single_find.class_name, single_find.function_name)
        if cache_key in block_lines_cache:
            # Retrieve from cache
            list_of_blocks = block_lines_cache[cache_key]
        else:
            # Use AST to find the start and end lines of the class or function.
            if single_find.class_name is not None or single_find.function_name is not None:
                list_of_blocks = astw.find_code_block(
                    file_path, class_name=single_find.class_name, function_name=single_find.function_name)
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
                if single_find.find_what in line:
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
                file_data[index] = file_data[index].replace(single_find.find_what, single_find.replace_to)

    file_io.write_file(content=file_data, file_path=file_path, encoding=encoding, convert_list_to_string=True)

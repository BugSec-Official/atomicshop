import json
from typing import Union

from .file_io import read_file_decorator, write_file_decorator


# noinspection PyUnusedLocal
@read_file_decorator
def read_json_file(
        file_path: str,
        file_mode: str = 'r',
        encoding=None,
        file_object=None,
        **kwargs
) -> dict:
    """
    Read the json file and return its content as dictionary.

    :param file_path: String with full file path to json file.
    :param file_mode: string, file reading mode. Examples: 'r', 'rb'. Default is 'r'.
    :param encoding: string, encoding of the file. Default is 'None'.
    :param file_object: file object of the 'open()' function in the decorator. Decorator executes the 'with open()'
        statement and passes to this function. That's why the default is 'None', since we get it from the decorator.
    :return: dict.
    """

    # Read the file to variable
    return json.load(file_object)


# noinspection PyUnusedLocal
@write_file_decorator
def write_json_file(
        json_content: Union[list, dict, str],
        file_path: str,
        file_mode: str = 'w',
        indent=None,
        encoding: str = None,
        use_default_indent=False,
        file_object=None,
        **kwargs
) -> None:
    """
    Export list or dict to json file. If indent specified, the content will be beautified by the number of spaces
    specified in 'indent' integer.

    Attention: 'output_dict_list' will be used by 'json.dump', it means that it must have dict / list of dicts as
    input and not json formatted string. Since, it is already formatted.

    :param json_content: can be list (of dictionaries) / dict / string (json formatted string).
        List of dicts is combined json.
    :param file_path: Full file path string to the file to output. Used in the decorator, then passed to this function.
    :param file_mode: string, file writing mode. Examples: 'x', 'w', 'wb'.
        Default is 'w'.
    :param indent: integer number of spaces for indentation.
        If 'ident=0' new lines still will be created. The most compact is 'indent=None' (from documentation)
        So, using default as 'None' and not something else.
    :param encoding: string, write the file with encoding. Example: 'utf-8'. 'None' is default, since it is default.
    :param use_default_indent: boolean. Default indent for 'json' format in many places is '2'. So, if you don't want
        to set 'indent=2', just set this to 'True'.
    :param file_object: file object of the 'open()' function in the decorator. Decorator executes the 'with open()'
        statement and passes to this function. That's why the default is 'None', since we get it from the decorator.
    :return:
    """

    if use_default_indent:
        indent = 2

    # Checking if 'json_content' is a list (of dictionaries) or it is a dictionary.
    if isinstance(json_content, list) or isinstance(json_content, dict):
        # In this case we'll use 'json.dump' to write python object to a file.
        # Getting the 'file_object' from the 'write_file_decorator'.
        json.dump(json_content, file_object, indent=indent)
    # Checking if 'json_content' is a string (json formatted).
    elif isinstance(json_content, str):
        # If so, write it to file as regular string.
        # Getting the 'file_object' from the 'write_file_decorator'.
        file_object.write(json_content)


def convert_dict_to_json_string(
        dict_or_list: Union[dict, list],
        indent=None,
        use_default_indent=False) -> str:
    """
    Convert dictionary or list of dictionaries to json formatted string.

    :param dict_or_list: dictionary or list of dictionaries to convert.
    :param indent: integer number of spaces for indentation.
        If 'ident=0' new lines still will be created. The most compact is 'indent=None' (from documentation)
        So, using default as 'None' and not something else.
    :param use_default_indent: boolean. Default indent for 'json' format in many places is '2'. So, if you don't want
        to set 'indent=2', just set this to 'True'.
    :return: json formatted string.
    """

    if use_default_indent:
        indent = 2

    return json.dumps(dict_or_list, indent=indent)


def convert_json_string_to_dict(json_string: str) -> dict:
    """
    Convert json formatted string to dictionary.

    :param json_string: json formatted string.
    :return: dictionary.
    """

    return json.loads(json_string)


def is_dict_json_serializable(
        dict_to_check: dict,
        raise_exception: bool = False
) -> tuple[bool, Union[str, None]]:
    """
    Check if dictionary is json serializable.

    :param dict_to_check: dictionary to check.
    :param raise_exception: boolean, if True, raise exception if dictionary is not json serializable.
    :return:
        boolean, True if dictionary is json serializable, False otherwise.
        string, error message if dictionary is not json serializable, None otherwise.
    """

    try:
        json.dumps(dict_to_check)
        return True, None
    except TypeError as e:
        if raise_exception:
            raise e
        else:
            return False, str(e)


def append_to_json(
        dict_or_list: Union[dict, list],
        json_file_path: str,
        indent=None,
        use_default_indent=False,
        enable_long_file_path=False,
        print_kwargs: dict = None
) -> None:
    """
    Append dictionary or list of dictionaries to json file.

    :param dict_or_list: dictionary or list of dictionaries to append.
    :param json_file_path: full file path to the json file.
    :param indent: integer number of spaces for indentation.
        If 'ident=0' new lines still will be created. The most compact is 'indent=None' (from documentation)
        So, using default as 'None' and not something else.
    :param use_default_indent: boolean. Default indent for 'json' format in many places is '2'. So, if you don't want
        to set 'indent=2', just set this to 'True'.
    :param enable_long_file_path: Boolean, by default Windows has a limit of 260 characters for file path. If True,
        the long file path will be enabled, and the limit will be 32,767 characters.
    :param print_kwargs: dict, the print_api arguments.
    :return:
    """

    # Read existing data from the file
    try:
        with open(json_file_path, 'r') as f:
            current_json_file = json.load(f)
    except FileNotFoundError:
        current_json_file: list = []

    # Append the new message to the existing data
    final_json_list_of_dicts: list[dict] = []
    if isinstance(current_json_file, list):
        current_json_file.append(dict_or_list)
        final_json_list_of_dicts = current_json_file
    elif isinstance(current_json_file, dict):
        final_json_list_of_dicts.append(current_json_file)
        final_json_list_of_dicts.append(dict_or_list)
    else:
        error_message = "The current file is neither a list nor a dictionary."
        raise TypeError(error_message)

    # Write the data back to the file
    write_json_file(
        final_json_list_of_dicts, json_file_path, indent=indent, use_default_indent=use_default_indent,
        enable_long_file_path=enable_long_file_path, **print_kwargs)
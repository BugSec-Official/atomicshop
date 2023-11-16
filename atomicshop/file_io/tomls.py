from datetime import date

try:
    # This is a library in python 3.11 and above.
    import tomllib
except ModuleNotFoundError:
    # This is library from pypi.
    import tomli as tomllib

from . import file_io


@file_io.read_file_decorator
def read_toml_file(file_path: str,
                   file_mode: str = 'rb',
                   encoding=None,
                   file_object=None,
                   **kwargs) -> dict:
    """
    Read the toml file and return its content as dictionary.

    :param file_path: String with full file path to file.
    :param file_mode: string, file reading mode. Examples: 'r', 'rb'. Default is 'r'.
    :param encoding: string, encoding of the file. Default is 'None'.
    :param file_object: file object of the 'open()' function in the decorator. Decorator executes the 'with open()'
        statement and passes to this function. That's why the default is 'None', since we get it from the decorator.
    :return: dict.
    """

    # Read the file to variable
    return tomllib.load(file_object)


@file_io.write_file_decorator
def write_toml_file(
        toml_content: dict,
        file_path: str,
        file_mode: str = 'w',
        encoding=None,
        file_object=None,
        **kwargs
) -> None:
    """
    Write the toml file with the specified content.

    :param toml_content: dict, content to write to the file.
    :param file_path: String with full file path to file.
    :param file_mode: string, file reading mode. Examples: 'w', 'wb'. Default is 'w'.
    :param encoding: string, encoding of the file. Default is 'None'.
    :param file_object: file object of the 'open()' function in the decorator. Decorator executes the 'with open()'
        statement and passes to this function. That's why the default is 'None', since we get it from the decorator.
    """

    # Write the file.
    file_object.write(dumps(toml_content))


def dumps(toml_dict: dict):
    """
    Dump the toml simple dictionary to string.
    The 'tomllib' library doesn't support dumping to string because of PEP680, so we will use this function.

    :param toml_dict: dict, toml dictionary to dump.
    :return: string, dumped toml dictionary.
    """

    def process_item(item_key, item_value):
        if isinstance(item_value, dict):
            toml_str = f'[{item_key}]\n'
            for sub_key, sub_value in item_value.items():
                toml_str += process_item(sub_key, sub_value)
            return toml_str
        elif isinstance(item_value, date):
            return f'{item_key} = {item_value.isoformat()}\n'
        elif item_value == '':
            return f"{item_key} = ''\n"
        elif isinstance(item_value, bool):
            return f'{item_key} = {str(item_value).lower()}\n'
        else:
            return f'{item_key} = {item_value}\n'

    toml_string = ''
    for key, value in toml_dict.items():
        toml_string += process_item(key, value)

    return toml_string

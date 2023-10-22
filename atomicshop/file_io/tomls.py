try:
    # This is a library in python 3.11 and above.
    import tomllib
except ModuleNotFoundError:
    # This is library from pypi.
    import tomli as tomllib

from .file_io import read_file_decorator


@read_file_decorator
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

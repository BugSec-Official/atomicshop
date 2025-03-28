from typing import Union
import functools
import os

from .. import print_api
from .. import inspect_wrapper


def get_write_file_mode_string_from_overwrite_bool(overwrite: bool) -> str:
    if overwrite:
        return 'w'
    else:
        return 'x'


def write_file_decorator(function_name):
    @functools.wraps(function_name)
    def wrapper_write_file_decorator(*args, **kwargs):
        # Put 'args' into 'kwargs' with appropriate key.
        # args, kwargs = put_args_to_kwargs(function_name, *args, **kwargs)
        args, kwargs = inspect_wrapper.get_target_function_default_args_and_combine_with_current(
            function_name, *args, **kwargs)

        print_api.print_api(message=f"Writing file: {kwargs['file_path']}", **kwargs)

        enable_long_file_path = kwargs.get('enable_long_file_path', False)
        if enable_long_file_path and os.name == 'nt':
            # A simpler string method would be to add '\\?\' to the beginning of the file path.
            # kwargs['file_path'] = rf"\\?\{kwargs['file_path']}"

            # Enable long file path.
            from ctypes import windll
            # Enable long file path.
            windll.kernel32.SetFileAttributesW(kwargs['file_path'], 0x80)

        try:
            with open(kwargs['file_path'], kwargs['file_mode'], encoding=kwargs['encoding']) as output_file:
                # Pass the 'output_file' object to kwargs that will pass the object to the executing function.
                kwargs['file_object'] = output_file
                # Since our 'kwargs' has already all the needed arguments, we don't need 'args'.
                function_name(**kwargs)
        # This exception is valid for file mode 'x' - Exclusive writing.
        except FileExistsError:
            message = f"Can't write file: {kwargs['file_path']}\n" \
                      f"File exists, you should enable force/overwrite mode."
            print_api.print_api(message, error_type=True, logger_method='critical', **kwargs)

    return wrapper_write_file_decorator


def read_file_decorator(function_name):
    @functools.wraps(function_name)
    def wrapper_read_file_decorator(*args, **kwargs):
        # Put 'args' into 'kwargs' with appropriate key.
        # args, kwargs = put_args_to_kwargs(function_name, *args, **kwargs)
        args, kwargs = inspect_wrapper.get_target_function_default_args_and_combine_with_current(
            function_name, *args, **kwargs)

        continue_loop: bool = True
        while continue_loop:
            try:
                print_api.print_api(message=f"Reading file: {kwargs['file_path']}", **kwargs)
                with open(kwargs['file_path'], kwargs['file_mode'], encoding=kwargs['encoding']) as input_file:
                    # Pass the 'output_file' object to kwargs that will pass the object to the executing function.
                    kwargs['file_object'] = input_file
                    # Since our 'kwargs' has already all the needed arguments, we don't need 'args'.
                    return function_name(**kwargs)
            except FileNotFoundError:
                message = f"File doesn't exist: {kwargs['file_path']}"
                print_api.print_api(message, error_type=True, logger_method='critical', **kwargs)
                raise
            except UnicodeDecodeError as exception_object:
                if kwargs["encoding"] != 'utf-8':
                    message = f'File decode error, current encoding: {kwargs["encoding"]}. Will try "utf-8".'
                    print_api.print_api(message, logger_method='error', **kwargs)
                    kwargs["encoding"] = 'utf-8'
                    pass
                    continue
                else:
                    message = f'File decode error.\n' \
                              f'{exception_object}'
                    print_api.print_api(message, merror_type=True, logger_method='critical', **kwargs)
                    continue_loop = False

    return wrapper_read_file_decorator


@write_file_decorator
def write_file(
        content: Union[str, list[str]],
        file_path: str,
        file_mode: str = 'w',
        encoding: str = None,
        enable_long_file_path: bool = False,
        file_object=None,
        **kwargs) -> None:
    """
    Export string to text file.

    :param content: string or list of strings, that includes formatted text content.
    :param file_path: Full file path string to the file to output. Used in the decorator, then passed to this function.
    :param file_mode: string, file writing mode. Examples: 'x', 'w', 'wb'.
        Default is 'w'.
    :param encoding: string, write the file with encoding. Example: 'utf-8'. 'None' is default, since it is default
        in 'open()' function.
    :param enable_long_file_path: Boolean, by default Windows has a limit of 260 characters for file path. If True,
        the long file path will be enabled, and the limit will be 32,767 characters.
    :param file_object: file object of the 'open()' function in the decorator. Decorator executes the 'with open()'
        statement and passes to this function. That's why the default is 'None', since we get it from the decorator.
    :return:
    """

    if isinstance(content, list):
        for line in content:
            if not line.endswith("\n"):
                file_object.write(line + "\n")
            else:
                file_object.write(line)
    elif isinstance(content, str):
        file_object.write(content)
    # THis will happen if the content is bytes and the file mode is 'wb'.
    elif isinstance(content, bytes) and 'b' in file_mode:
        file_object.write(content)
    else:
        raise TypeError(f"Content type is not supported: {type(content)}")


@read_file_decorator
def read_file(file_path: str,
              file_mode: str = 'r',
              encoding=None,
              read_to_list: bool = False,
              file_object=None,
              **kwargs) -> Union[str, bytes, list]:
    """
    Read file and return its content as string.

    :param file_path: String with full file path to read.
    :param file_mode: string, file reading mode. Examples: 'r', 'rb'. Default is 'r'.
    :param encoding: string, read the file with encoding. Example: 'utf-8'. 'None' is default, since it is default
        in 'open()' function.
    :param read_to_list: Boolean, if True, the file will be read to list of strings, each string is a line.
    :param file_object: file object of the 'open()' function in the decorator. Decorator executes the 'with open()'
        statement and passes to this function. That's why the default is 'None', since we get it from the decorator.
    :return: string or list of strings.
    """

    # Read the file to variable.
    if read_to_list:
        # This method avoids creating an intermediary list by directly reading and processing the file within the list
        # comprehension.
        result = [line.rstrip() for line in file_object]
    else:
        result = file_object.read()

    return result

import sys
from typing import Union

from .print_api import print_api


def get_current_python_version_string() -> str:
    """
    Function gets version MAJOR.MINOR.MICRO from 'sys.version_info' object and returns it as a string.
    :return: python MAJOR.MINOR.MICRO version string.
    """

    return f'{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}'


# noinspection PyUnusedLocal
def check_if_version_object_is_tuple_or_string(version_object: any,
                                               **kwargs) -> tuple:
    """
    Function checks if 'version_object' that was passed is tuple or string.
    If it's tuple then returns it back. If it's string, converts to tuple then returns it.
    If the object is none of the above, returns None.

    :param version_object: Can be string ('3.10') or tuple of integers ((3, 10)).
    :return:
    """
    # Check if tuple was passed.
    if isinstance(version_object, tuple):
        return version_object
    else:
        # Then check if a string was passed.
        if isinstance(version_object, str):
            # The check will be against tuple of integers, so we'll convert a string to tuple of integers.
            return tuple(map(int, version_object.split('.')))
        else:
            message = f'[*] Function: [check_if_version_object_is_tuple_or_string]\n' \
                      f'[*] [version_object] object passed is not tuple or string.\n' \
                      f'[*] Object type: {type(version_object)}\n' \
                      f'[*] Object content {version_object}\n' \
                      f'Exiting...'
            print_api(message, error_type=True, logger_method='critical', **kwargs)

            return None


# noinspection PyUnusedLocal
def check_python_version_compliance(
        minimum_version: Union[str, tuple] = None,
        maximum_version: Union[str, tuple] = None,
        minor_version: Union[str, tuple] = None,
        **kwargs
) -> bool:
    """
    Python version check. Should be executed before importing external libraries, since they depend on Python version.

    :param minimum_version: Can be string ('3.10') or tuple of integers ((3, 10)).
    :param maximum_version: Can be string ('3.10') or tuple of integers ((3, 10)).
        If maximum version is not specified, it will be considered as all versions above the minimum are compliant.
    :param minor_version: Can be string ('3.10') or tuple of integers ((3, 10)).
        If minor version is specified, it will be considered as all the versions with the same major, minor version
        are compliant. Example: if minor_version is '3.10', then all the versions with '3.10.x' are compliant.
    :return:
    """

    if not minimum_version and not maximum_version and not minor_version:
        raise ValueError("At least one of the version parameters should be passed.")

    if minor_version and (minimum_version or maximum_version):
        raise ValueError("Minor version should be passed alone.")

    # Check objects for string or tuple and get the tuple.
    if minimum_version:
        minimum_version_scheme: tuple = check_if_version_object_is_tuple_or_string(minimum_version, **kwargs)
    else:
        minimum_version_scheme = tuple()
    # If 'maximum_version' object was passed, check it for string or tuple and get the tuple.
    if maximum_version:
        maximum_version_scheme: tuple = check_if_version_object_is_tuple_or_string(maximum_version, **kwargs)
    else:
        maximum_version_scheme = tuple()

    # If 'minor_version' object was passed, check it for string or tuple and get the tuple.
    if minor_version:
        minor_version_scheme: tuple = check_if_version_object_is_tuple_or_string(minor_version, **kwargs)
    else:
        minor_version_scheme = tuple()

    # Get current python version.
    python_version_full: str = get_current_python_version_string()

    message = f"[*] Current Python Version: {python_version_full}"
    print_api(message, logger_method='info', **kwargs)

    if minor_version_scheme:
        # Check if current python version is later or equals to the minimum required version.
        if sys.version_info[:2] != minor_version_scheme:
            message = f"[!!!] YOU NEED TO INSTALL ANY PYTHON " \
                      f"[{'.'.join(str(i) for i in minor_version_scheme)}] version, " \
                      f"to work properly."
            print_api(message, error_type=True, logger_method='critical', **kwargs)

            return False
    elif minimum_version_scheme and maximum_version_scheme:
        if not sys.version_info >= minimum_version_scheme or not sys.version_info < maximum_version_scheme:
            message = f"[!!!] YOU NEED TO INSTALL AT LEAST PYTHON " \
                      f"[{'.'.join(str(i) for i in minimum_version_scheme)}], " \
                      f"AND EARLIER THAN [{'.'.join(str(i) for i in maximum_version_scheme)}], " \
                      f"to work properly."
            print_api(message, error_type=True, logger_method='critical', **kwargs)

            return False
    elif minimum_version_scheme and not maximum_version_scheme:
        if not sys.version_info >= minimum_version_scheme:
            message = f"[!!!] YOU NEED TO INSTALL AT LEAST PYTHON " \
                      f"[{'.'.join(str(i) for i in minimum_version_scheme)}], " \
                      f"to work properly."
            print_api(message, error_type=True, logger_method='critical', **kwargs)

            return False
    elif not minimum_version_scheme and maximum_version_scheme:
        if not sys.version_info < maximum_version_scheme:
            message = f"[!!!] YOU NEED TO INSTALL EARLIER THAN PYTHON " \
                      f"[{'.'.join(str(i) for i in maximum_version_scheme)}], " \
                      f"to work properly."
            print_api(message, error_type=True, logger_method='critical', **kwargs)

            return False

    message = "[*] Version Check PASSED."
    print_api(message, logger_method='info', **kwargs)

    return True

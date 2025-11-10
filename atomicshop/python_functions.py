import sys
from typing import Union

from .print_api import print_api


def get_python_version_string() -> str:
    """
    Function gets version MAJOR.MINOR.MICRO from 'sys.version_info' object and returns it as a string.
    :return: python MAJOR.MINOR.MICRO version string.
    """

    return f'{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}'


def check_python_version_compliance(
        min_ver: tuple = None,
        max_ver: tuple = None,
) -> str | None:
    """
    Python version check. Should be executed before importing external libraries, since they depend on Python version.

    :param min_ver: tuple of integers (3, 10).
    :param max_ver: tuple of integers (3, 10).
        If maximum version is not specified, it will be considered as all versions above the minimum are compliant.
    :return: If version is not compliant, returns string with error message. Otherwise, returns None.
    """

    if not min_ver and not max_ver:
        raise ValueError("At least one of the version parameters should be passed.")

    current_version_info: tuple = sys.version_info[:3]
    if min_ver and not max_ver:
        if current_version_info < min_ver:
            return f'Python version {".".join(map(str, min_ver))} or higher is required. '\
                   f'Current version is {".".join(map(str, current_version_info))}.'
    elif max_ver and not min_ver:
        if current_version_info > max_ver:
            return f'Python version up to {".".join(map(str, max_ver))} is required. '\
                   f'Current version is {".".join(map(str, current_version_info))}.'
    elif min_ver and max_ver:
        if not (min_ver <= current_version_info <= max_ver):
            return f'Python version between {".".join(map(str, min_ver))} and '\
                   f'{".".join(map(str, max_ver))} is required. '\
                   f'Current version is {".".join(map(str, current_version_info))}.'
    else:
        return None

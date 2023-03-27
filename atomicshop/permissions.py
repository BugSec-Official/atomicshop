# v1.0.3 - 27.03.2023 00:10
import os

from .print_api import print_api


# noinspection PyUnusedLocal
def check_admin(**kwargs) -> bool:
    """
    Function checks on Windows or POSIX OSes if the script is executed under Administrative Privileges.
    :return: True / False.
    """

    function_result: bool = False

    if os.name == 'nt':
        try:
            # Only admins can read "C:\Windows\temp" folder.
            # Getting 'windir' environment variable.
            windows_directory: str = os.environ['windir']
            windows_temp_path: str = windows_directory + os.sep + "temp"

            print_api(f"Checking path for reading: {windows_temp_path}", **kwargs)

            # Only Windows users with admin privileges can read the "C:\windows\temp"
            temp = os.listdir(windows_temp_path)
        except PermissionError:
            function_result = False
        else:
            function_result = True
    else:
        if 'SUDO_USER' in os.environ and os.geteuid() == 0:
            function_result = True
        else:
            function_result = False

    message = f"Administrative Privileges: {function_result}"
    print_api(message, **kwargs)

    return function_result

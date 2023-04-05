import os
import ctypes


def is_admin() -> bool:
    """
    Function checks on Windows or POSIX OSes if the script is executed under Administrative Privileges.
    :return: True / False.
    """

    if os.name == 'nt':
        if ctypes.windll.shell32.IsUserAnAdmin() == 0:
            result = False
        else:
            result = True
    else:
        if 'SUDO_USER' in os.environ and os.geteuid() == 0:
            result = True
        else:
            result = False

    return result

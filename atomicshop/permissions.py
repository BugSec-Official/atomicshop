import os
import ctypes
import contextlib


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


@contextlib.contextmanager
def temporary_regular_permissions():
    """
    This function is used to temporarily change the effective user and group ID to the original user's.
    This is used to run commands with the original user's permissions.
    If you executed a script with 'sudo' and wanted certain action to execute as regular user and not root.

    Example:
        with temporary_regular_permissions():
            # Do something with regular permissions.
            pass

    :return:
    """
    # Save the current effective user and group ID
    original_euid, original_egid = os.geteuid(), os.getegid()

    try:
        # Get the original user's UID and GID
        orig_uid = int(os.environ.get('SUDO_UID', os.getuid()))
        orig_gid = int(os.environ.get('SUDO_GID', os.getgid()))

        # Set the effective user and group ID to the original user's
        os.setegid(orig_gid)
        os.seteuid(orig_uid)

        # Provide the context to do something with these permissions
        yield
    finally:
        # Revert to the original effective user and group ID
        os.seteuid(original_euid)
        os.setegid(original_egid)

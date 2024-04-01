import os
import sys
import stat
import ctypes
import contextlib
import subprocess

from . import process
from .print_api import print_api


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


def request_sudo_on_ubuntu_by_python():
    """
    The function tries to request sudo on Ubuntu for the user to enter the password, by executing python executable
    with sudo.

    :return:
    """

    try:
        # Attempt to re-execute the script using sudo
        subprocess.check_call(['sudo', 'python3'] + sys.argv)
    except subprocess.CalledProcessError:
        # Handle the error in case sudo command fails (e.g., wrong password)
        print_api("Failed to gain sudo access. Please try again.", color='red')
        sys.exit(1)


def request_sudo_on_ubuntu_by_bash():
    """
    The function tries to request sudo on Ubuntu for the user to enter the password, by executing appropriate
    bash commands.

    :return:
    """

    script = """
    if [ "$EUID" -ne 0 ]; then
      echo "This script requires root privileges. Please enter your password for sudo access."
      sudo -v
      while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &
    fi
    # Your bash commands that require sudo here
    """

    process.execute_script(script, shell=True)


def set_executable_permission(file_path: str):
    """
    Function sets the executable permission on a file.
    Equivalent to: chmod +x <file_path>

    :param file_path: str, path to the file.
    :return:
    """

    # os.chmod(file_path, os.stat(file_path).st_mode | 0o111)
    os.chmod(file_path, os.stat(file_path).st_mode | stat.S_IXUSR)


def is_executable_permission(file_path: str) -> bool:
    """
    Function checks if the file has the executable permission.
    Equivalent to: stat -c "%a %n" <file_path>

    :param file_path: str, path to the file.
    :return: bool, True / False.
    """

    return bool(os.stat(file_path).st_mode & stat.S_IXUSR)


def run_as_root(command):
    subprocess.check_call(['sudo'] + command)


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

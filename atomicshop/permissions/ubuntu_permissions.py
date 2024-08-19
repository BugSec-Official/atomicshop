import os
import stat
import contextlib
import subprocess

# Import pwd only on linux.
if os.name == 'posix':
    import pwd


def get_sudo_executer_username() -> str:
    """
    Function gets the username of the user who executed the script with sudo.
    :return: str, username.
    """

    if 'SUDO_USER' in os.environ:
        return os.environ['SUDO_USER']
    else:
        return ''


def set_executable(file_path: str):
    """
    Function sets the executable permission on a file.
    Equivalent to: chmod +x <file_path>

    :param file_path: str, path to the file.
    :return:
    """

    # os.chmod(file_path, os.stat(file_path).st_mode | 0o111)
    os.chmod(file_path, os.stat(file_path).st_mode | stat.S_IXUSR)


def change_file_owner(file_path: str, username: str):
    """
    Function changes the owner of the file to the specified user.
    :param file_path: str, path to the file.
    :param username: str, username of the new owner.
    :return:
    """

    uid = pwd.getpwnam(username).pw_uid
    os.chown(file_path, uid, -1)


def is_executable(file_path: str) -> bool:
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


def expand_user_path(user_name, path):
    pwnam = pwd.getpwnam(user_name)
    home_dir = pwnam.pw_dir
    return path.replace("~", home_dir)

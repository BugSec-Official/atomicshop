import os
import stat
import contextlib
import subprocess
import getpass

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


def detect_current_user(
        optional_env_user_var: str = 'CUSTOM_SCRIPTED_USER'
) -> str:
    """
    Try to robustly determine the 'real' installing user.

    Priority:
      1. FDB_INSTALL_USER env var (explicit override).
      2. If running as root with sudo: use SUDO_USER.
      3. Otherwise: use effective uid.
      4. Fallbacks: getpass.getuser() / $USER.

    :param optional_env_user_var: str, name of the environment variable that can override the user detection.
    :return: str, username.
    """

    # 1. Explicit override for weird environments (CI, containers, etc.)
    env_user = os.getenv(optional_env_user_var)
    if env_user:
        return env_user

    # 2. If we are root, prefer the sudo caller if any
    try:
        euid = os.geteuid()
    except AttributeError:  # non-POSIX, very unlikely here
        euid = None

    if euid == 0:
        sudo_user = os.environ.get("SUDO_USER")
        if sudo_user:
            return sudo_user

    # 3. Normal case: effective uid -> username
    if euid is not None:
        try:
            return pwd.getpwuid(euid).pw_name
        except Exception:
            pass

    # 4. Fallbacks that don’t depend on utmp/tty
    try:
        return getpass.getuser()
    except Exception:
        return os.environ.get("USER", "unknown")


def set_executable(file_path: str):
    """
    Function sets the executable permission on a file.
    Equivalent to: chmod +x <file_path>

    :param file_path: str, path to the file.
    :return:
    """

    # os.chmod(file_path, os.stat(file_path).st_mode | 0o111)
    os.chmod(file_path, os.stat(file_path).st_mode | stat.S_IXUSR)


def set_trusted_executable(file_path: str):
    """
    Function sets the executable permission on a file and marks it as trusted.
    :param file_path: str, path to the file.
    :return:
    """

    # Check if the file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file does not exist: {file_path} ")

    # Execute the `gio set` command
    subprocess.run(
        ["gio", "set", file_path, "metadata::trusted", "true"],
        check=True
    )


def set_xfce_exe_checksum(desktop_file_path):
    # Expand `~` to the full home directory path
    desktop_file_path = os.path.expanduser(desktop_file_path)

    # Ensure the file exists
    if not os.path.exists(desktop_file_path):
        raise FileNotFoundError(f"The file does not exist: {desktop_file_path} ")

    # Calculate the SHA256 checksum of the file
    result = subprocess.run(
        ["sha256sum", desktop_file_path],
        stdout=subprocess.PIPE,
        check=True,
        text=True
    )
    checksum = result.stdout.split()[0]

    # Set the metadata::xfce-exe-checksum attribute using `gio`
    subprocess.run(
        ["gio", "set", "-t", "string", desktop_file_path, "metadata::xfce-exe-checksum", checksum],
        check=True
    )


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


def set_folder_permissions(
        folder_path: str,
        username: str = None,
        logged_in_non_sudo_user: bool = False
):
    """
    Set ownership and permissions for an existing folder.

    :param folder_path: Path to the folder (must already exist)
    :param username: Username to assign ownership to (ignored if non_sudo_user=True)
    :param logged_in_non_sudo_user: If True, use the current logged-in user unless running under sudo
    """

    if not username and not logged_in_non_sudo_user:
        raise ValueError("A username must be provided, or 'non_sudo_user' must be set to True.")

    # Handle non_sudo_user case
    if logged_in_non_sudo_user:
        # Get the current logged-in user
        username = pwd.getpwuid(os.getuid())[0]

    # Get the UID and GID of the specified user
    user_info = pwd.getpwnam(username)
    user_uid = user_info.pw_uid
    user_gid = user_info.pw_gid

    # Change ownership of the folder to the specified user
    # print(f"Changing ownership of {folder_path} to user '{username}'...")
    os.chown(folder_path, user_uid, user_gid)

    # Set appropriate permissions (read, write, execute for the owner)
    # print(f"Setting permissions for {folder_path}...")
    os.chmod(folder_path, 0o755)  # Owner rwx, group r-x, others r-x

    # print(f"Ownership and permissions updated for folder: '{folder_path}'")


def is_directory_owner(directory_path: str, username: str) -> bool:
    """
    Function checks if the directory is owned by the specified user.
    :param directory_path: str, path to the directory.
    :param username: str, username of the user.
    :return: bool, True / False.
    """

    uid = pwd.getpwnam(username).pw_uid
    return os.stat(directory_path).st_uid == uid

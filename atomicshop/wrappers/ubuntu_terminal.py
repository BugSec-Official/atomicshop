import os
import sys
import subprocess
import shutil
import time

from ..print_api import print_api
from ..permissions import ubuntu_permissions


def install_packages(package_list: list[str]):
    """
    Function installs a package using apt-get.
    :param package_list: list of strings, package names to install.
    :return:
    """

    # Construct the command with the package list
    command = ["sudo", "apt-get", "install", "-y"] + package_list

    subprocess.check_call(command)


def remove_packages(
        package_list: list[str],
        remove_config_files: bool = False,
        remove_dependencies: bool = False,
):
    """
    Function removes a list of packages.
    :param package_list: list of strings, package names to remove. Regular removal is through 'apt remove'.
    :param remove_config_files: bool, if True, the config files will be removed also through 'apt purge'.
    :param remove_dependencies: bool, if True, the dependencies will be removed also through 'apt autoremove'.
    :return:
    """

    # Construct the command with the package list
    command = ["sudo", "apt", "remove", "-y"] + package_list

    # If remove_config_files is True, add 'purge' to the command
    if remove_config_files:
        command.insert(2, "purge")

    subprocess.check_call(command)

    # If remove_dependencies is True, remove the dependencies
    if remove_dependencies:
        subprocess.check_call(["sudo", "apt", "autoremove", "-y"])


def is_package_installed(package: str) -> bool:
    """
    Function checks if a package is installed.
    :param package: str, package name.
    :return:
    """

    try:
        # Run the dpkg-query command to check if the package is installed
        result = subprocess.run(
            ['apt', '-qq', 'list', '--installed', package], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # If the return code is 0 and the output contains 'install ok installed', the package is installed
        if result.returncode == 0 and result.stdout != b'':
            return True
        else:
            return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False


def is_package_in_apt_cache(package: str) -> bool:
    try:
        # Run the apt-cache show command to check if the package exists
        result = subprocess.run(['apt-cache', 'show', package], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # If the return code is 0 and the output contains package information, it exists
        if result.returncode == 0 and b'Package:' in result.stdout:
            return True
        else:
            return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False


def is_executable_exists(package: str) -> bool:
    """
    Function checks if a package is installed.
    :param package: str, package name.
    :return:
    """

    if not shutil.which(package):
        return False
    else:
        return True


def update_system_packages():
    """
    Function updates the system packages.
    :return:
    """
    subprocess.check_call(['sudo', 'apt-get', 'update'])


def upgrade_system_packages(apt_update: bool = True):
    """
    Function upgrades the system packages.
    :param apt_update: bool, if True, the system packages will be updated before upgrading.
        Before upgrading the system packages, you need to update the package list first.
    :return:
    """

    if apt_update:
        update_system_packages()

    subprocess.check_call(['sudo', 'apt-get', 'upgrade', '-y'])


def is_service_running(service_name: str, user_mode: bool = False, return_false_on_error: bool = False) -> bool:
    """
    Function checks if a service is running.
    :param service_name: str, the service name.
    :param user_mode: bool, if True, the service will be checked in user mode.
    :param return_false_on_error: bool, if True, the function will return False if an error occurs.
    :return:
    """

    command: list = ['systemctl']

    if user_mode:
        command.append('--user')

    command.extend(['is-active', service_name])

    try:
        # Use subprocess to run 'systemctl is-active' and capture its output
        status = subprocess.check_output(command, text=True).strip()
    except subprocess.CalledProcessError as e:
        if return_false_on_error:
            # Handle error if systemctl command fails
            return False
        else:
            # Raise the exception if return_false_on_error is False
            raise e

    if status == "active":
        return True
    else:
        return False


def enable_service(service_name: str, sudo: bool = False, user_mode: bool = False):
    """
    Function enables a service.
    :param service_name: str, the service name.
    :param sudo: bool, if True, the command will be executed with sudo.
    :param user_mode: bool, if True, the service will be enabled in user mode.
    :return:
    """

    command: list = []

    if sudo:
        command.append('sudo')

    command.append('systemctl')

    if user_mode:
        command.append('--user')

    command.extend(['enable', service_name])

    subprocess.check_call(command)


def start_service(service_name: str, sudo: bool = False, user_mode: bool = False):
    """
    Function starts a service.
    :param service_name: str, the service name.
    :param sudo: bool, if True, the command will be executed with sudo.
    :param user_mode: bool, if True, the service will be started in user mode.
    :return:
    """

    command: list = []

    if sudo:
        command.append('sudo')

    command.append('systemctl')

    if user_mode:
        command.append('--user')

    command.extend(['start', service_name])

    subprocess.check_call(command)


def start_enable_service_check_availability(
        service_name: str,
        wait_time_seconds: float = 30,
        exit_on_error: bool = True,
        start_service_bool: bool = True,
        enable_service_bool: bool = True,
        check_service_running: bool = True,
        user_mode: bool = False,
        sudo: bool = True,
        print_kwargs: dict = None
):
    """
    Function starts and enables a service and checks its availability.

    :param service_name: str, the service name.
    :param wait_time_seconds: float, the time to wait after starting the service before checking the service
        availability.
    :param exit_on_error: bool, if True, the function will exit the program if the service is not available.
    :param start_service_bool: bool, if True, the service will be started.
    :param enable_service_bool: bool, if True, the service will be enabled.
    :param check_service_running: bool, if True, the function will check if the service is running.
    :param user_mode: bool, if True, the service will be started and enabled in user mode.
    :param sudo: bool, if True, the command will be executed with sudo.
    :param print_kwargs: dict, the print arguments.
    :return:
    """

    if not start_service_bool and not enable_service_bool:
        raise ValueError("Either 'start_service_bool' or 'enable_service_bool' must be True.")

    # Start and enable the service.
    if start_service_bool:
        start_service(service_name, user_mode=user_mode, sudo=sudo)
    if enable_service_bool:
        enable_service(service_name, user_mode=user_mode,sudo=sudo)

    if check_service_running:
        print_api(
            f"Waiting {str(wait_time_seconds)} seconds for the program to start before availability check...",
            **(print_kwargs or {}))
        time.sleep(wait_time_seconds)

        if not is_service_running(service_name, user_mode=user_mode):
            print_api(
                f"[{service_name}] service failed to start.", color='red', error_type=True, **(print_kwargs or {}))
            if exit_on_error:
                sys.exit(1)
        else:
            print_api(f"[{service_name}] service is running.", color='green', **(print_kwargs or {}))


def add_path_to_bashrc(as_regular_user: bool = False):
    """Add $HOME/bin to the PATH in .bashrc if it's not already present.
    :param as_regular_user: bool, if True, the function will run as a regular user even if executed with sudo.
    """
    home_path_bashrc = "~/.bashrc"

    if as_regular_user:
        # Get the current non-sudo user
        with ubuntu_permissions.temporary_regular_permissions():
            current_non_sudo_user = os.getlogin()

        # Get the home path of the current non-sudo user
        user_bashrc_path = ubuntu_permissions.expand_user_path(current_non_sudo_user, home_path_bashrc)
    else:
        user_bashrc_path = os.path.expanduser(home_path_bashrc)

    new_path = 'export PATH=$PATH:$HOME/bin\n'
    with open(user_bashrc_path, 'r+') as bashrc:
        content = bashrc.read()
        if "$HOME/bin" not in content:
            bashrc.write(new_path)
            print("Added $HOME/bin to .bashrc")
        else:
            print("$HOME/bin already in .bashrc")


def add_line_to_bashrc(line: str, as_regular_user: bool = False):
    """Add a line to the .bashrc file.
    :param line: str, the line to add to the .bashrc file.
    :param as_regular_user: bool, if True, the function will run as a regular user even if executed with sudo.
    """
    home_path_bashrc = "~/.bashrc"

    if as_regular_user:
        # Get the current non-sudo user
        with ubuntu_permissions.temporary_regular_permissions():
            current_non_sudo_user = os.getlogin()

        # Get the home path of the current non-sudo user
        user_bashrc_path = ubuntu_permissions.expand_user_path(current_non_sudo_user, home_path_bashrc)
    else:
        user_bashrc_path = os.path.expanduser(home_path_bashrc)

    with open(user_bashrc_path, 'r+') as bashrc:
        content = bashrc.read()
        if line not in content:
            bashrc.write(line)
            print(f"Added line to .bashrc: {line}")
        else:
            print(f"Line already in .bashrc: {line}")


def get_command_execution_as_sudo_executer(command: str, add_bash_exec: bool = False) -> str:
    """
    Function gets the command execution as the sudo executer.
    The input command should be without 'sudo', if it will be, it will be omitted.
    :param command: str, the command to execute.
    :param add_bash_exec: bool, if True, the command will be executed with bash.
        Example command: 'systemctl --user start docker.service'
        Example command with add_bash_exec: 'su <sudo_executioner_user> -c "/bin/bash systemctl --user start docker.service"'
        Example command without add_bash_exec: 'su <sudo_executioner_user> -c "systemctl --user start docker.service"'
    :return: str, the command execution as the sudo executer.
    """

    if command.startswith('sudo'):
        if command.startswith('sudo -'):
            raise ValueError("The command should not start with 'sudo -'.")

        command = command.replace('sudo ', '').strip()

    sudo_executer_username: str = ubuntu_permissions.get_sudo_executer_username()

    if sudo_executer_username:
        if add_bash_exec:
            command = f'/bin/bash {command}'
        return f'su {sudo_executer_username} -c "{command}"'
    else:
        return command


def is_sudo_file_exists(file_path: str) -> bool:
    """
    Function checks if a file exists with sudo permissions.
    :param file_path: str, the file path.
    :return:
    """

    try:
        _ = subprocess.run(['sudo', 'test', '-e', file_path], check=True)
        return True
    except subprocess.CalledProcessError:
        return False

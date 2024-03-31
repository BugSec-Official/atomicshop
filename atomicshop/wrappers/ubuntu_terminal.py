import sys
import subprocess
import shutil
import time

from ..print_api import print_api


def install_packages(package_list: list[str]):
    """
    Function installs a package using apt-get.
    :param package_list: list of strings, package names to install.
    :return:
    """

    # Construct the command with the package list
    command = ["sudo", "apt-get", "install", "-y"] + package_list

    subprocess.check_call(command)


def is_package_installed(package: str) -> bool:
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


def upgrade_system_packages():
    """
    Function upgrades the system packages.
    :return:
    """
    subprocess.check_call(['sudo', 'apt-get', 'upgrade', '-y'])


def is_service_running(service_name: str, return_false_on_error: bool = False) -> bool:
    try:
        # Use subprocess to run 'systemctl is-active' and capture its output
        status = subprocess.check_output(['systemctl', 'is-active', service_name], text=True).strip()
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


def enable_service(service_name: str):
    """
    Function enables a service.
    :param service_name: str, the service name.
    :return:
    """
    subprocess.check_call(['sudo', 'systemctl', 'enable', service_name])


def start_service(service_name: str):
    """
    Function starts a service.
    :param service_name: str, the service name.
    :return:
    """
    subprocess.check_call(['sudo', 'systemctl', 'start', service_name])


def start_enable_service_check_availability(
        service_name: str,
        wait_time_seconds: float = 30,
        exit_on_error: bool = True,
        start_service_bool: bool = True,
        enable_service_bool: bool = True,
        check_service_running: bool = True,
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
    :param print_kwargs: dict, the print arguments.
    :return:
    """

    if not start_service_bool and not enable_service_bool:
        raise ValueError("Either 'start_service_bool' or 'enable_service_bool' must be True.")

    # Start and enable the service.
    if start_service_bool:
        start_service(service_name)
    if enable_service_bool:
        enable_service(service_name)

    if check_service_running:
        print_api(
            f"Waiting {str(wait_time_seconds)} seconds for the program to start before availability check...",
            **(print_kwargs or {}))
        time.sleep(wait_time_seconds)

        if not is_service_running(service_name):
            print_api(
                f"[{service_name}] service failed to start.", color='red', error_type=True, **(print_kwargs or {}))
            if exit_on_error:
                sys.exit(1)
        else:
            print_api(f"[{service_name}] service is running.", color='green', **(print_kwargs or {}))

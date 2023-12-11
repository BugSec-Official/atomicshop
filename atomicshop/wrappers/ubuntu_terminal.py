import subprocess
import shutil


def install_package(package: str):
    """
    Function installs a package using apt-get.
    :param package: str, package name.
    :return:
    """
    subprocess.check_call(['sudo', 'apt-get', 'install', '-y', package])


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

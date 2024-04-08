import subprocess
import sys


def install_packages_with_current_interpreter(
        package_name_list: list[str],
        user: bool = False,
        upgrade: bool = False
):
    """
    This function will install the packages with the current interpreter.
    :param package_name_list: list, the list of package names to install.
    :param user: bool, if True, the packages will be installed for the current user.
    :param upgrade: bool, if True, the packages will be upgraded.
    :return:
    """

    commands: list[str] = [sys.executable, "-m", "pip", "install"]

    if user:
        commands.append("--user")
    if upgrade:
        commands.append("--upgrade")

    for package_name in package_name_list:
        subprocess.check_call([*commands, package_name])

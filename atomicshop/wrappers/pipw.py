import subprocess
import sys


def install_packages_with_current_interpreter(
        package_name_list: list[str] = None,
        user: bool = False,
        upgrade: bool = False,
        prefer_binary: bool = False,
        requirements_file_path: str = None
):
    """
    This function will install the packages with the current interpreter.
    :param package_name_list: list, the list of package names to install.
    :param user: bool, if True, the packages will be installed for the current user.
    :param upgrade: bool, if True, the packages will be upgraded.
    :param prefer_binary: bool, if True, the binary packages will be preferred.
    :param requirements_file_path: string, the path to the requirements file.
    :return:
    """

    commands: list[str] = [sys.executable, "-m", "pip", "install"]

    if user:
        commands.append("--user")
    if upgrade:
        commands.append("--upgrade")
    if prefer_binary:
        commands.append("--prefer-binary")
    if requirements_file_path:
        commands.append("-r")
        commands.append(requirements_file_path)

    if package_name_list:
        for package_name in package_name_list:
            subprocess.check_call([*commands, package_name])
    else:
        subprocess.check_call(commands)

import subprocess
import sys


def install_packages_with_current_interpreter(package_name_list: list[str]):
    for package_name in package_name_list:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])

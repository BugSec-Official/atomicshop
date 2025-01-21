import subprocess
import requests
import argparse

from ...basics import booleans
from .. import githubw, ubuntu_terminal
from ...print_api import print_api


def is_nodejs_installed():
    """
    The function will check if Node.js is installed.
    :return: bool.
    """

    try:
        # Run the command 'node -v'
        result = subprocess.run(['node', '-v'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Check if the command was successful
        if result.returncode == 0:
            message = f"Node.js installed. Version: {result.stdout.strip()}"
            print_api(message, color='green')
            return True
        else:
            print_api("Node.js is not installed.")
            return False
    except FileNotFoundError:
        print_api("Node command not found. Node.js is not installed.")
        return False


def get_nodejs_latest_version_number(
        by_github_api: bool = True,
        _by_nodejs_website: bool = False,
        get_major: bool = False
) -> str:
    """
    The function will get the latest version number of Node.js.
    :param by_github_api: bool, if True, the function will get the version number using the GitHub API.
        Limitations: rate limits apply.
    :param _by_nodejs_website: bool, if True, the function will get the version number using the Node.js website.
        Limitations: the website structure can change and the json file is relatively large.
        This is only for reference, it is not tested.
    :param get_major: bool, if True, the function will return only the major version number string.
    :return: str.
    """

    if by_github_api and _by_nodejs_website:
        raise ValueError("Only one of the arguments can be True.")
    elif not by_github_api and not _by_nodejs_website:
        raise ValueError("At least one of the arguments must be True.")

    latest_version = ''
    if by_github_api:
        github_wrapper = githubw.GitHubWrapper('nodejs', 'node')
        latest_version = github_wrapper.get_the_latest_release_version_number()
    elif _by_nodejs_website:
        url = "https://nodejs.org/dist/index.json"
        response = requests.get(url)
        versions = response.json()
        latest_version = versions[0]['version']  # Assuming the first one is the latest.

    if get_major:
        latest_version = latest_version.replace('v', '')
        latest_version = latest_version.split('.')[0]

    return latest_version


def install_nodejs_ubuntu(
        install_latest_version: bool = False,
        install_lts: bool = True,
        install_by_version_number: str = None,
        force_install: bool = False
):
    """
    The function will install Node.js on Ubuntu.

    :param install_latest_version: bool, if True, the function will install the latest version of Node.js.
    :param install_lts: bool, if True, the function will install the LTS version of Node.js.
    :param install_by_version_number: str, the version number of Node.js to install.
    :param force_install: bool, if True, the function will install Node.js even if it is already installed.

    :return:
    """

    booleans.is_only_1_true_in_list(
        booleans_list_of_tuples=[
            (install_latest_version, 'install_latest_version'),
            (install_lts, 'install_lts'),
            (install_by_version_number, 'install_by_version_number')
        ],
        raise_if_all_false=True
    )

    # Check if Node.js is already installed.
    if is_nodejs_installed():
        if not force_install:
            return

    # NodeSource is listed as source under official Node.js GitHub repository:
    # https://github.com/nodejs/node?tab=readme-ov-file#current-and-lts-releases
    print_api("Adding NodeSource repository...")

    # Fetch and execute the NodeSource repository setup script.
    if install_latest_version:
        install_by_version_number: str = get_nodejs_latest_version_number(get_major=True)

    command: str = ''
    if install_latest_version or install_by_version_number:
        command = f"curl -fsSL https://deb.nodesource.com/setup_{install_by_version_number}.x | sudo -E bash -"
    elif install_lts:
        command = "curl -fsSL https://deb.nodesource.com/setup_current.x | sudo -E bash -"

    _ = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)

    ubuntu_terminal.update_system_packages()
    ubuntu_terminal.install_packages(['nodejs'])

    # Check if Node.js is installed.
    is_nodejs_installed()


def install_nodejs_main():
    """
    The function will install Node.js on Ubuntu.
    :return:
    """

    # Create the parser.
    parser = argparse.ArgumentParser(description="Install Node.js on Ubuntu.")
    parser.add_argument(
        '--latest',
        action='store_true',
        help="Install the latest version of Node.js."
    )
    parser.add_argument(
        '--lts',
        action='store_true',
        help="Install the LTS version of Node.js."
    )
    parser.add_argument(
        '--version',
        type=str,
        help="Install a specific version of Node.js."
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help="Force the installation of Node.js."
    )

    # Parse the arguments.
    args = parser.parse_args()

    install_nodejs_ubuntu(
        install_latest_version=args.latest,
        install_lts=args.lts,
        install_by_version_number=args.version,
        force_install=args.force
    )


def install_npm_package_ubuntu(package_name: str, sudo: bool = True):
    """
    The function will install a npm package on Ubuntu.
    :param package_name: str, the name of the package to install.
    :param sudo: bool, if True, the function will use sudo.
        NPM commands require sudo to install global packages.
    :return:
    """

    # Check if Node.js is installed.
    if not is_nodejs_installed():
        return

    command = f"npm install -g {package_name}"

    if sudo:
        command = f"sudo {command}"

    _ = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)

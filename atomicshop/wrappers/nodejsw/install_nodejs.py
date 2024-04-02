import subprocess
import getpass

from ... import process, filesystem, permissions
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


def install_nodejs_ubuntu():
    """
    The function will install Node.js on Ubuntu.
    :return:
    """

    # Check if Node.js is already installed.
    if is_nodejs_installed():
        return

    # Add the Node.js repository.
    process.run_command(['curl', '-sL', 'https://deb.nodesource.com/setup_14.x', '-o', '/tmp/nodesource_setup.sh'])
    process.run_command(['bash', '/tmp/nodesource_setup.sh'])

    # Install Node.js
    process.run_command(['apt-get', 'install', '-y', 'nodejs'])

    # Check if Node.js is installed.
    is_nodejs_installed()
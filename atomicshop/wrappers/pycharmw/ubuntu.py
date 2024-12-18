import argparse

from ... import process
from ...print_api import print_api


def parse_args():
    """
    Parse command line arguments.

    :return: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description='Install PyCharm Community Edition.')
    parser.add_argument('-ic', '--install_community', action='store_true', required=True,
                        help='Install PyCharm Community Edition with snapd.')
    parser.add_argument('--enable_sudo_execution', action='store_true',
                        help='There is a problem when trying to run snapd installed Pycharm as sudo, need to enable '
                             'this.')

    return parser.parse_args()


def install_main():
    """
    Main function to install the latest PyCharm Community Edition.

    Usage:
    python -m atomicshop.a_installs.ubuntu.pycharm
    """

    args = parse_args()

    if args.install_community:
        process.execute_script('sudo snap install pycharm-community --classic', shell=True)

    if args.enable_sudo_execution:
        process.execute_script('xhost +SI:localuser:root', shell=True)
        print_api('Run the following command to start PyCharm as root: [sudo snap run pycharm-community]', color='blue')
    return 0

import os

from .file_io import tomls
from . import filesystem
from . import print_api

CONFIG_FILE_NAME = 'config.toml'
CONFIG: dict = dict()


def get_config(script_directory: str = None, config_file_name: str = CONFIG_FILE_NAME) -> dict:
    """
    Get the config file content.

    :param script_directory: string, path to the script directory. Default is None. If None, the function will
        get the working directory instead.
    :param config_file_name: string, name of the config file. Default is 'config.toml' as specified in the constant:
        'CONFIG_FILE_NAME'.
    :return: dict.
    """

    global CONFIG

    # Get working directory if script directory wasn't specified.
    if not script_directory:
        script_directory = filesystem.get_working_directory()

    CONFIG = tomls.read_toml_file(f'{script_directory}{os.sep}{config_file_name}')
    return CONFIG


def write_config(
        config: dict,
        script_directory: str = None,
        config_file_name: str = CONFIG_FILE_NAME,
        print_message: bool = True
):
    """
    Write the config file with the specified content.

    :param config: dict, content to write to the file.
    :param script_directory: string, path to the script directory. Default is None. If None, the function will
        get the working directory instead.
    :param config_file_name: string, name of the config file. Default is 'config.toml' as specified in the constant:
        'CONFIG_FILE_NAME'.
    :param print_message: boolean, if True, the function will print the message about the created config file.
        Also, it will wait for the user to press Enter to exit the script.
        If False, the function will not print anything and will not exit.
    :return:
    """

    global CONFIG
    CONFIG = config

    # Get working directory if script directory wasn't specified.
    if not script_directory:
        script_directory = filesystem.get_working_directory()

    config_file_path = f'{script_directory}{os.sep}{config_file_name}'

    if not filesystem.is_file_exists(config_file_path):
        tomls.write_toml_file(config, f'{script_directory}{os.sep}{config_file_name}')

        if print_message:
            print_api.print_api(f"Created config file: {config_file_path}", color="yellow")
            print_api.print_api(f"You need to fill it with details.", color="yellow")
            input("Press Enter to exit.")
            exit()

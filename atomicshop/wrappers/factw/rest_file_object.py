# noinspection PyPackageRequirements
import requests

from . import fact_config, get_file_data
from ... print_api import print_status_of_list


def is_uid_exist(uid: str):
    """
    Check if the specified FACT UID exists in the FILE_OBJECT database.
    :param uid: string, FACT UID.
    :return: boolean, True if exists, False if not.
    """

    url: str = f'{fact_config.FACT_ADDRESS}{fact_config.FILE_OBJECT_ENDPOINT}/{uid}'
    response: requests.Response = requests.get(url)

    # Check response status code.
    if response.status_code == 200:
        return True
    else:
        return False


def is_file_object_exist(directory_path: str, firmwares: list = None) -> list:
    """
    Check if the specified FACT UID exists in the FILE_OBJECT database.
    :param directory_path: string, path to directory with firmware binary files.
    :param firmwares: list, list of dictionaries with firmware file paths and hashes.
        Example:
        [
            {
                'path': 'C:\\Users\\user\\Desktop\\firmware.bin',
                'uid': 'SHA256HASH_BINARYLENGTH'
            },
            {
                'path': 'C:\\Users\\user\\Desktop\\firmware2.bin',
                'uid': 'SHA256HASH_BINARYLENGTH2'
            }
        ]

    :return:
    """

    firmwares = get_file_data.get_file_data(directory_path, firmwares)

    uid_exist_list: list = list()
    # Check if the files already exist in the database.
    for file_index, firmware in enumerate(firmwares):
        print_status_of_list(
            list_instance=firmwares, prefix_string='Checking UID in FILE_OBJECT DB: ', current_state=(file_index + 1))
        if is_uid_exist(firmware['uid']):
            uid_exist_list.append(firmware)

    # If there are files that already exist in the database, print them and raise an exception.
    if uid_exist_list:
        # Print just the file path and the UID.
        list_to_print: list = list()
        for firmware in uid_exist_list:
            list_to_print.append({
                'path': firmware['path'],
                'uid': firmware['uid']
            })

        # Raise exception for the list of lists.
        message = f'Files that already exist in the database were found:\n'
        for entry in list_to_print:
            message += f'{entry}\n'

        raise ValueError(message)

    return firmwares

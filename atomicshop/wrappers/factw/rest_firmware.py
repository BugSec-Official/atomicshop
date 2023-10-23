# noinspection PyPackageRequirements
import requests
import base64
import time

from . import fact_config, get_file_data, rest_file_object
from ... print_api import print_api, print_status_of_list
from ... file_io import file_io
from ... import filesystem


def is_analysis_finished(uid: str) -> bool:
    """
    Check if currently running analysis is running.
    :param uid: string, FACT UID.
    :return: boolean, True if finished, False if not.
    """

    url: str = f'{fact_config.FACT_ADDRESS}{fact_config.STATUS_ENDPOINT}'

    # Check if currently running analysis is finished
    response = requests.get(url)
    status = response.json()
    recently_finished = status["system_status"]["backend"]["analysis"]["recently_finished_analyses"]
    current_analyses = status["system_status"]["backend"]["analysis"]["current_analyses"]
    return uid in recently_finished or current_analyses == {}


def wait_for_analysis(uid: str):
    """
    Wait for analysis to finish.
    :param uid: string, FACT UID.
    :return: None.
    """

    print_api(f'Waiting for analysis to finish: {uid}')
    time.sleep(30)
    while not is_analysis_finished(uid):
        time.sleep(30)

    print_api(f'Analysis finished: {uid}', color='green')


def upload_firmware(
        firmware_file_path: str,
        json_data: dict,
        use_all_analysis_systems: bool = False,
        firmware_binary: bytes = None,
        wait_for_analysis_completion: bool = True
):
    """
    Upload firmware binary file to the server.

    :param firmware_file_path: Path to firmware file.
    :param use_all_analysis_systems: Use all analysis systems.
    :param json_data: dict, of Parameters to pass for REST API:
        {
            "device_name": <string>,
            "device_part": <string>,           # new in FACT 2.5
            "device_class": <string>,
            "file_name": <string>,
            "version": <string>,               # supersedes firmware_version field
            "vendor": <string>,
            "release_date": <string>,
            "tags": <string>,
            "requested_analysis_systems": <list>,
            "binary": <string(base64)>
        }

        'device_name' and 'tags' aren't required.
        'binary' and 'file_name' is filled by this function from the firmware file.
        'requested_analysis_systems' is filled by this function if 'use_all_analysis_systems' is True.

        Example from https://github.com/fkie-cad/FACT_core/wiki/Rest-API#restfirmwareuid:
        {
            "device_name": "rest_test",
            "device_part": <string>,
            "device_class": "Router",
            "file_name": "firmware.bin",
            "version": "1.1",
            "vendor": "AVM",
            "release_date": "2011-01-01",
            "tags": "tag1,tag2",
            "requested_analysis_systems": ["file_type", "file_hashes"],
            "binary": "dGVzdDEyMzQgdBzb21lIHRlc3QgZQ=="
        }
    :param firmware_binary: bytes, binary content of the firmware file. If not specified, it will be read from the file.
    :param wait_for_analysis_completion: Wait for analysis to finish.
        It is not advised to upload a lot of files at once, since it
        can bloat the memory and cause the server to crash. Default is True.

    :return: None.
    """

    url: str = f'{fact_config.FACT_ADDRESS}{fact_config.FIRMWARE_ENDPOINT}'

    if 'release_date' not in json_data:
        json_data['release_date'] = '1970-01-01'

    # Add all analysis systems to the list.
    if use_all_analysis_systems:
        # There is also a system known as 'unpacker', but it is not a real plugin, so it is not needed to be executed.
        # In older versions it led to exception.
        json_data['requested_analysis_systems'] = [
            'binwalk', 'cpu_architecture', 'crypto_hints', 'crypto_material', 'cve_lookup', 'cwe_checker',
            'device_tree', 'elf_analysis', 'exploit_mitigations', 'file_hashes', 'file_system_metadata',
            'file_type', 'hardware_analysis', 'hashlookup', 'information_leaks', 'init_systems', 'input_vectors',
            'interesting_uris', 'ip_and_uri_finder', 'ipc_analyzer', 'kernel_config', 'known_vulnerabilities',
            'printable_strings', 'qemu_exec', 'software_components', 'source_code_analysis', 'string_evaluator',
            'tlsh', 'users_and_passwords'
        ]

    # Open firmware file.
    if firmware_binary is None:
        firmware_binary: bytes = file_io.read_file(firmware_file_path, file_mode='rb')

    # Encode firmware file to base64.
    json_data['binary'] = base64.b64encode(firmware_binary).decode()

    print_api(f'Uploading: {firmware_file_path}')
    # Send firmware file to the server.
    response = requests.put(url, json=json_data)

    try:
        uid = response.json()['uid']
    except KeyError:
        raise requests.exceptions.HTTPError(f'Error: {response.json()}')

    # Check response status code.
    if response.status_code == 200:
        print_api('Upload successful: 200')
        if wait_for_analysis_completion:
            wait_for_analysis(uid)
    else:
        # Print error.
        # print_api('Error: ' + str(response.status_code), error_type=True, logger_method='critical')
        raise requests.exceptions.HTTPError(f'Error: {response.status_code}')

    return response


def upload_files(directory_path: str, json_data: dict):
    """
    Upload firmware binary files from specified directory to the server.
    :param directory_path: string, path to directory with firmware binary files.
    :param json_data: dict of REST params.
    :return:
    """

    # Get firmwares and check for duplicate files.
    firmwares, _ = filesystem.find_duplicates_by_hash(
        directory_path, recursive=False, add_binary=True, raise_on_found=True)

    # Get filenames of firmwares.
    for firmware in firmwares:
        firmware['file_name'] = filesystem.get_file_name_with_extension(firmware['path'])

    # Check if UID is already in the database.
    is_firmware_exist(directory_path=directory_path, firmwares=firmwares)
    rest_file_object.is_file_object_exist(directory_path=directory_path, firmwares=firmwares)

    use_all_analysis_systems: bool = False
    for file_index, firmware in enumerate(firmwares):
        print_status_of_list(
            list_instance=firmwares, prefix_string=f'Uploading File: ', current_state=(file_index + 1), same_line=False)

        json_data['file_name'] = firmware['file_name']

        if json_data['requested_analysis_systems'] == 'all' and not use_all_analysis_systems:
            use_all_analysis_systems = True

        upload_firmware(
            firmware['path'], json_data=json_data, use_all_analysis_systems=use_all_analysis_systems,
            firmware_binary=firmware['binary']
        )

    return None


def is_uid_exist(uid: str):
    """
    Check if the specified FACT UID exists in the FIRMWARE database.
    :param uid: string, FACT UID.
    :return: boolean, True if exists, False if not.
    """

    url: str = f'{fact_config.FACT_ADDRESS}{fact_config.FIRMWARE_ENDPOINT}/{uid}'
    response: requests.Response = requests.get(url)

    # Check response status code.
    if response.status_code == 200:
        return True
    else:
        return False


def is_firmware_exist(directory_path: str, firmwares: list = None) -> list:
    # noinspection GrazieInspection
    """
        Check if there are files that have exactly the same hash, then check if the files already exist in the database.
        :param directory_path: string, path to directory with firmware binary files.
        :param firmwares: list, list of dictionaries with firmware file paths and hashes.
            Example:
            [
                {
                    'path': 'C:\\Users\\user\\Desktop\\firmware.bin',
                    'hash': 'SHA256_HASH',
                    'binary': b'FIRMWARE_BINARY'
                },
                {
                    'path': 'C:\\Users\\user\\Desktop\\firmware2.bin',
                    'hash': 'SHA256_HASH2',
                    'binary': b'FIRMWARE_BINARY2'
                }
            ]

        :return:
        """

    firmwares = get_file_data.get_file_data(directory_path, firmwares)

    uid_exist_list: list = list()
    # Check if the files already exist in the database.
    for file_index, firmware in enumerate(firmwares):
        print_status_of_list(
            list_instance=firmwares, prefix_string='Checking UID in FIRMWARE DB: ', current_state=(file_index + 1))
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
        message = f'Files already exist in the FIRMWARE database:\n'
        for entry in list_to_print:
            message += f'{entry}\n'

        raise ValueError(message)

    return firmwares

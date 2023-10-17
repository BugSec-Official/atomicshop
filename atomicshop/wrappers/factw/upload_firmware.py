import requests
import base64

from . import fact_config
from ... print_api import print_api
from ... file_io import file_io


def upload_firmware(firmware_file_path: str, params: dict, use_all_analysis_systems: bool = False):
    """
    Upload firmware binary file to the server.

    :param firmware_file_path: Path to firmware file.
    :param use_all_analysis_systems: Use all analysis systems.
    :param params: Parameters:
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

    :return: None.
    """

    url: str = f'{fact_config.FACT_ADDRESS}{fact_config.FIRMWARE_ENDPOINT}'

    # Add all analysis systems to the list.
    if use_all_analysis_systems:
        params['requested_analysis_systems'] = [
            'binwalk', 'cpu_architecture', 'crypto_hints', 'crypto_material', 'cve_lookup', 'cwe_checker',
            'device_tree', 'elf_analysis', 'exploit_mitigations', 'file_hashes', 'file_system_metadata',
            'file_type', 'hardware_analysis', 'hashlookup', 'information_leaks', 'init_systems', 'input_vectors',
            'interesting_uris', 'ip_and_uri_finder', 'ipc_analyzer', 'kernel_config', 'known_vulnerabilities',
            'printable_strings', 'qemu_exec', 'software_components', 'source_code_analysis', 'string_evaluator',
            'tlsh', 'unpacker', 'users_and_passwords'
        ]

    # Open firmware file.
    firmware_binary_content = file_io.read_file(firmware_file_path, file_mode='rb')
    # Encode firmware file to base64.
    params['binary'] = base64.b64encode(firmware_binary_content)

    print_api(f'Uploading: {firmware_file_path}')
    # Send firmware file to the server.
    response = requests.put(
        url,
        params=params,
    )

    # Check response status code.
    if response.status_code == 200:
        # Print response.
        print_api(response.json())
    else:
        # Print error.
        print_api('Error: ' + str(response.status_code), error_type=True, logger_method='critical')

    return response

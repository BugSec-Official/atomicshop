# noinspection PyPackageRequirements
import requests
import base64
import time
from typing import Union
import os

from .. import config_fact, get_file_data
from . import file_object
from ....print_api import print_api, print_status_of_list
from ....file_io import file_io, jsons, csvs
from ....basics import dicts
from .... import filesystem, ip_addresses


def get_uid_list(
        config_data: dict,
        query: Union[dict, str] = None,
        url_parameters: dict = None,
        fetch_uid_data: bool = False
):
    """
    Get firmware UIDs by query.
    :param config_data: dict, of Parameters to pass for REST API.
        If query is specified, this parameter is ignored.
    :param query: string, query.
        Example:
            {$and: [{"device_name": "test"}, {"device_name": "test222"}]}
        Info:
            Return UIDs of all firmwares with device_name "test" and device_name "test222".

        Example2:
            {"vendor": "AVM"}
        Info:
            Return UIDs of all firmwares with vendor "AVM".

        Operators:
            $and: AND operator.
            $or: OR operator.
            $ne: NOT EQUAL operator.
            $like: LIKE operator.
            $in: IN operator.
            &lt: LESS THAN operator.
            $gt: GREATER THAN operator.
            $exists: EXISTS operator.
            $regex: REGEX operator.
            $contains: CONTAINS operator.
            Basically all the operators that are supported by the MongoDB.

    :param url_parameters: dict, of URL parameters. Available parameters:
        {
            'limit': int - limit of results,
            'offset': int - offset of results (paging),
            'recursive': boolean - recursive search - only with query,
            'inverted': boolean - inverted search - only with query and recursive
        }

    :param fetch_uid_data: boolean, get data of the UIDs. This can take time, since each UID will be queried against the
        database. Default is False.
    :return: list, list of UIDs.
    """

    url: str = f'{config_fact.FACT_ADDRESS}{config_fact.FIRMWARE_ENDPOINT}'

    if query is None:
        if 'requested_analysis_systems' in config_data:
            dicts.remove_keys(config_data, ['requested_analysis_systems'])

        query = config_data

    if isinstance(query, dict):
        query = jsons.convert_dict_to_json_string(query)
    elif isinstance(query, str):
        pass
    else:
        raise TypeError(f'Query must be dict or string, not {type(query)}')

    # If there are parameters to add to the URL, add the '?' to the URL.
    if url_parameters or query:
        url = f'{url}?'

    # Add parameters to the URL.
    if url_parameters and query:
        for key, value in url_parameters.items():
            url = f'{url}{key}={str(value)}&'
            url = f'{url}query={query}'
    if url_parameters and not query:
        for parameter_index, (key, value) in enumerate(url_parameters.items()):
            url = f'{url}{key}={str(value)}'
            if parameter_index < len(url_parameters) - 1:
                url = f'{url}&'
    elif query and not url_parameters:
        url = f'{url}query={query}'

    response: requests.Response = requests.get(url)

    uids: list = list()
    # Check response status code.
    if response.status_code == 200:
        uids: list = response.json()['uids']
        # Print response.
        # print_api(response.json())
        print_api(f'Found {len(uids)} UIDs.')
    else:
        # Print error.
        print_api('Error: ' + str(response.status_code), error_type=True, logger_method='critical')

    if fetch_uid_data:
        return get_uid_list_data(uids)
    else:
        return uids


def is_analysis_finished(uid: str) -> bool:
    """
    Check if currently running analysis is running.
    :param uid: string, FACT UID.
    :return: boolean, True if finished, False if not.
    """

    url: str = f'{config_fact.FACT_ADDRESS}{config_fact.STATUS_ENDPOINT}'

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

    url: str = f'{config_fact.FACT_ADDRESS}{config_fact.FIRMWARE_ENDPOINT}'

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
    file_object.is_file_object_exist(directory_path=directory_path, firmwares=firmwares)

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


def get_uid_data(uid: str):
    """
    Get firmware data by UID.
    :param uid: string, FACT UID.
    :return:
    """

    url: str = f'{config_fact.FACT_ADDRESS}{config_fact.FIRMWARE_ENDPOINT}/{uid}'
    response: requests.Response = requests.get(url)

    # Check response status code.
    if response.status_code == 200:
        return response.json()
    else:
        return None


def get_uid_list_data(uid_list: list):
    """
    Get firmware data for each UID in the list.
    :param uid_list: list, list of FACT UIDs.
    :return:
    """

    uid_data_list: list = list()
    for uid_index, uid in enumerate(uid_list):
        print_status_of_list(
            list_instance=uid_list, prefix_string='Getting UID Data: ', current_state=(uid_index + 1))
        uid_data_list.append(get_uid_data(uid))

    return uid_data_list


def is_uid_exist(uid: str):
    """
    Check if the specified FACT UID exists in the FIRMWARE database.
    :param uid: string, FACT UID.
    :return: boolean, True if exists, False if not.
    """

    if get_uid_data(uid):
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


def find_analysis_recursively(uid: str, object_path: str = str()):
    """
    The function will find the analysis information like cve, OS type, etc. recursively and return it to
    the asker firmware.

    :param uid: string of the uid of the file_object.
    :param object_path: string of the path of the file_object. Can be empty on the first iteration since it's the same
        UID as the first asker function.
    :return:
    """

    found_info: dict = dict()

    # Get the data of the firmware.
    file_data: dict = file_object.get_uid_data(uid)

    # Add current path to the object path to create a full path of the current object.
    current_path: str = object_path + file_data['file_object']['meta_data']['hid']
    print_api(f"Current File: {current_path}", print_end='\r')

    cve_lookup_result: dict = file_data['file_object']['analysis']['cve_lookup']['result']
    ip_and_uri_finder_result: dict = file_data['file_object']['analysis']['ip_and_uri_finder']['result']
    software_components_result: dict = file_data['file_object']['analysis']['software_components']['result']

    if cve_lookup_result and 'skipped' not in cve_lookup_result.keys():
        if cve_lookup_result['cve_results']:
            found_info['cve_lookup'] = file_data['file_object']['analysis']['cve_lookup']['result']
    if ip_and_uri_finder_result and 'skipped' not in ip_and_uri_finder_result.keys():
        if ip_and_uri_finder_result['ips_v4'] or ip_and_uri_finder_result['ips_v6'] or ip_and_uri_finder_result['uris']:
            found_info['ip_and_uri_finder'] = file_data['file_object']['analysis']['ip_and_uri_finder']['result']
    if software_components_result and 'skipped' not in software_components_result.keys():
        found_info['software_components'] = file_data['file_object']['analysis']['software_components']['result']

    if found_info:
        found_info['path'] = current_path
        found_files: list = [found_info]
    else:
        found_files: list = list()

    for included_file_uid in file_data['file_object']['meta_data']['included_files']:
        # Get the data of the included file.
        included_found_files = find_analysis_recursively(included_file_uid, (
                object_path + file_data['file_object']['meta_data']['hid']))

        if included_found_files:
            found_files.extend(included_found_files)

    return found_files


def save_firmware_uids_as_csv(
        directory_path: str,
        config_data: dict = None,
        query: Union[dict, str] = None,
        url_parameters: dict = None,
        get_analysis_data: bool = False
):
    """
    Save firmware UIDs as CSV file.
    :param directory_path: string, path to save the CSV file.
    :param config_data: check get_uid_list() for more info.
    :param query: check get_uid_list() for more info.
    :param url_parameters: check get_uid_list() for more info.
    :param get_analysis_data: boolean. If 'True', the function will get the analysis data of each file that is found
        in the firmware results. This is needed in order to determine if the firmware is vulnerable to CVEs, OS type,
        etc. Default is 'False'.
        NOTE: This can take a lot of time, since each internal file will be queried against the database.

    :return:
    """

    uids: list = get_uid_list(
        config_data=config_data, query=query, url_parameters=url_parameters, fetch_uid_data=True)

    export_list: list = list()
    for uid_index, uid in enumerate(uids):
        print_status_of_list(
            list_instance=uids, prefix_string='Checking UID for analysis items: ', current_state=(uid_index + 1),
            same_line=False)
        export_entry: dict = dict()
        for key, value in uid['firmware']['meta_data'].items():
            if key == 'included_files' or key == 'total_files_in_firmware':
                continue
            export_entry[key] = value

        export_entry['mime'] = uid['firmware']['analysis']['file_type']['result']['mime']
        export_entry['sha256'] = uid['firmware']['analysis']['file_hashes']['result']['sha256']
        export_entry['uid'] = uid['request']['uid']

        # Check for CVEs and other info recursively.
        if get_analysis_data:
            analysis_data_list = find_analysis_recursively(uid['request']['uid'])
        else:
            analysis_data_list = list()

        export_entry['urls_ips']: list = list()
        export_entry['cves']: list = list()
        export_entry['software']: list = list()

        for analysis_data in analysis_data_list:
            if 'cve_lookup' in analysis_data:
                for key, value in analysis_data['cve_lookup']['cve_results'].items():
                    export_entry['cves'] = [key, jsons.convert_dict_to_json_string(value)]
            if 'software_components' in analysis_data:
                for key, value in analysis_data['software_components'].items():
                    export_entry['software'] = [key, jsons.convert_dict_to_json_string(value['meta'])]
            if 'ip_and_uri_finder' in analysis_data:
                for key, value in analysis_data['ip_and_uri_finder'].items():
                    if not value:
                        continue

                    if key == 'ips_v4':
                        for ipv4s in analysis_data['ip_and_uri_finder']['ips_v4']:
                            for ip_address in ipv4s:
                                if ip_addresses.is_ip_address(ip_address, ip_type='ipv4'):
                                    if ip_address not in export_entry['urls_ips']:
                                        export_entry['urls_ips'].append(ip_address)
                    elif key == 'ips_v6':
                        for ipv6s in analysis_data['ip_and_uri_finder']['ips_v6']:
                            for ip_address in ipv6s:
                                if ip_addresses.is_ip_address(ip_address, ip_type='ipv6'):
                                    if ip_address not in export_entry['urls_ips']:
                                        export_entry['urls_ips'].append(ip_address)
                    elif key == 'uris':
                        for address in value:
                            if address not in export_entry['urls_ips']:
                                export_entry['urls_ips'].append(address)

        export_list.append(export_entry)
        # break

    # Save UIDs as CSV file.
    file_path = directory_path + os.sep + 'uids.csv'
    csvs.write_list_to_csv(export_list, file_path)

    return None

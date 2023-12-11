import time
from typing import Union
import os

from . import included_files, fw_files, virtual_file_path, file_object, analysis
from .. import config_fact, get_file_data
from ....print_api import print_api, print_status_of_list
from ....file_io import file_io, jsons, csvs
from ....basics import dicts
from .... import filesystem, ip_addresses
from ...psycopgw import psycopgw


def get_firmware_uid_data(uid: str, config_db: dict, get_fw_file_data: bool = False) -> dict:
    """
    Get all the possible Firmware UID data from all the tables.
    :param uid: string, UID of the firmware.
    :param config_db: dict, database configuration.
    :param get_fw_file_data: bool, get firmware file data. This is a very slow process, so it's disabled by default.
    :return: dict, firmware data.
    """

    firmware_data: dict = dict()
    firmware_data['summary'] = dict()

    firmware_data['summary'] = get_firmwares(config_db=config_db, uid=uid)[0]

    # Get included files with virtual file path.
    firmware_data['included_files'] = virtual_file_path.get_virtual_path(config_db=config_db, parent_uid=uid)
    firmware_data['number_of_included_files'] = len(firmware_data['included_files'])

    # Get firmware files.
    firmware_data['fw_files'] = fw_files.get_fw_uids(uid=uid, config_db=config_db, get_only_uids=False)
    firmware_data['number_of_fw_files'] = len(firmware_data['fw_files'])

    # Get file object.
    firmware_data['file_object'] = file_object.get_file_object(uid=uid, config_db=config_db)

    # Get analysis.
    firmware_data['analysis'] = analysis.get_analysis(uid=uid, config_db=config_db)

    # Get summary.
    firmware_data['summary']['file_name'] = firmware_data['file_object'][0]['file_name']
    firmware_data['summary']['uid'] = firmware_data['file_object'][0]['uid']
    firmware_data['summary']['sha256'] = firmware_data['file_object'][0]['sha256']
    firmware_data['summary']['size'] = firmware_data['file_object'][0]['size']
    firmware_data['summary']['number_of_included_files'] = firmware_data['number_of_included_files']
    firmware_data['summary']['number_of_fw_files'] = firmware_data['number_of_fw_files']

    for analysis_entry in firmware_data['analysis']:
        if analysis_entry['plugin'] == 'file_type':
            firmware_data['summary']['file_type'] = analysis_entry['summary'][0]
            break

    # Get firmware file data.
    if get_fw_file_data:
        firmware_files: list = list()
        for uid_index, firmware_file in enumerate(firmware_data['fw_files']):
            print_status_of_list(
                list_instance=firmware_data['fw_files'], prefix_string='Checking Internal Files for analysis items: ',
                current_state=(uid_index + 1))
            firmware_files.append(get_file_object_uid_data(uid=firmware_file['file_uid'], config_db=config_db))

        firmware_data['fw_files_data'] = firmware_files
        firmware_data['analysis_items'] = get_analysis_items(firmware_data['fw_files_data'], firmware_data['analysis'])

        for key, value in firmware_data['analysis_items'].items():
            firmware_data['summary'][key] = value
    else:
        firmware_data['fw_files_data'] = list()
        firmware_data['analysis_items'] = dict()
        firmware_data['summary']['urls_ips'] = list()
        firmware_data['summary']['software'] = list()
        firmware_data['summary']['cves'] = list()

    return firmware_data


def get_file_object_uid_data(uid: str, config_db: dict) -> dict:
    """
    Get all the possible Firmware UID data from all the tables.
    :param uid: string, UID of the firmware.
    :param config_db: dict, database configuration.
    :return: dict, firmware data.
    """

    file_data: dict = dict()

    # Get included files with virtual file path.
    file_data['included_files'] = virtual_file_path.get_virtual_path(config_db=config_db, parent_uid=uid)
    file_data['number_of_included_files'] = len(file_data['included_files'])

    # Get file object.
    file_data['file_object'] = file_object.get_file_object(uid=uid, config_db=config_db)

    # if firmware_data['file_object'][0]['file_name'] == 'exec.bin':
    #     pass

    # Get analysis.
    file_data['analysis'] = analysis.get_analysis(uid=uid, config_db=config_db)

    return file_data


def get_firmwares(config_db: dict, uid: str = None, config_data: dict = None, query: str = None) -> list:
    """
    Get all firmwares from the database.
    :param config_db: dict, database configuration.
    :param uid: string, firmware UID. If None, get all the UIDs.
    :param config_data: dict, config data to fetch from the database.
    :param query: string, query to filter the results. You can specify SQL query directly to the database.
        Example: "SELECT * FROM firmware WHERE vendor = 'Siemens'"
    :return: list, list of dictionaries with firmware data.
    """

    if not config_data:
        config_data = dict()

    if query is None:
        if 'requested_analysis_systems' in config_data:
            dicts.remove_keys(config_data, ['requested_analysis_systems'])

        query = "SELECT * FROM firmware"

        if len(config_data) == 1:
            for key, value in config_data.items():
                if isinstance(value, str):
                    query += f" WHERE {key} = '{value}'"
                else:
                    query += f" WHERE {key} = {value}"
        elif len(config_data) > 1:
            query += " WHERE "
            for key, value in config_data.items():
                if isinstance(value, str):
                    query += f"{key} = '{value}' AND "
                else:
                    query += f"{key} = {value} AND "

            # Remove the last ' AND ' from the query.
            query = query[:-5]

        if uid and len(config_data) > 0:
            query += f" AND uid = '{uid}'"
        elif uid and len(config_data) == 0:
            query += f" WHERE uid = '{uid}'"

    firmwares: list = psycopgw.get_query_data(
        query=query, dbname=config_db['database'], user=config_db['ro-user'], password=config_db['ro-pw'],
        host=config_db['server'], port=config_db['port'], leave_connected=True)

    return firmwares


def get_analysis_items(fw_list: list, parent_analysis_items: list = None) -> dict:
    """
    The function will find the analysis information like cve, OS type, etc. for all the files inside firmware and
    return it to the asker firmware.

    :param fw_list: list of files inside firmware.
    :param parent_analysis_items: list of analysis items from the parent firmware to include in the result.
        This is important, since maybe the result of the parent will include important items for the analysis
        final result.

    :return: list of analysis items.
    """

    def get_analysis_info(analysis_items: list):
        for analysis_item in analysis_items:
            if analysis_item['plugin'] == 'ip_and_uri_finder' and analysis_item['summary']:
                if analysis_item['result']['ips_v4']:
                    for ipv4s in analysis_item['result']['ips_v4']:
                        for ip_address in ipv4s:
                            if ip_addresses.is_ip_address(ip_address, ip_type='ipv4'):
                                if ip_address not in found_info['urls_ips']:
                                    found_info['urls_ips'].append(ip_address)
                if analysis_item['result']['ips_v6']:
                    for ipv6s in analysis_item['result']['ips_v6']:
                        for ip_address in ipv6s:
                            if ip_addresses.is_ip_address(ip_address, ip_type='ipv6'):
                                if ip_address not in found_info['urls_ips']:
                                    found_info['urls_ips'].append(ip_address)
                if analysis_item['result']['uris']:
                    for address in analysis_item['result']['uris']:
                        if address not in found_info['urls_ips']:
                            found_info['urls_ips'].append(address)
            elif analysis_item['plugin'] == 'software_components' and analysis_item['summary']:
                for key, value in analysis_item['result'].items():
                    found_info['software'] = [key, jsons.convert_dict_to_json_string(value['meta'])]
            elif analysis_item['plugin'] == 'cve_lookup' and analysis_item['summary']:
                for key, value in analysis_item['result']['cve_results'].items():
                    found_info['cves'] = [key, jsons.convert_dict_to_json_string(value)]

    found_info: dict = dict()
    found_info['urls_ips'] = list()
    found_info['software'] = list()
    found_info['cves'] = list()

    for firmware_analysis in fw_list:
        print_api(f"Current File: {firmware_analysis['file_object'][0]['file_name']}", print_end='\r')

        # if firmware_analysis['file_object'][0]['file_name'] == 'zlib_decompressed':
        #     pass

        get_analysis_info(firmware_analysis['analysis'])

    if parent_analysis_items:
        get_analysis_info(parent_analysis_items)

    return found_info


def save_firmware_uids_as_csv(
        directory_path: str,
        fact_path: str,
        config_data: dict = None,
        query: str = None
):
    """
    Save firmware UIDs as CSV file.
    :param directory_path: string, path to save the CSV file.
    :param fact_path: string, path to 'FACT_core' including.
    :param config_data: check get_firmwares() for more info. The default is None, in this case all the firmwares will be
        exported.
    :param query: string, check 'get_firmwares()' for more info.

    :return:
    """

    # Get fact config data.
    fact_config_data: dict = config_fact.get_config_data(fact_path)

    # Get firmwares by config or query.
    uids: list = get_firmwares(config_db=fact_config_data['common']['postgres'], config_data=config_data, query=query)

    export_list: list = list()
    for uid_index, uid in enumerate(uids):
        print_status_of_list(
            list_instance=uids, prefix_string='Getting Firmware UID: ', current_state=(uid_index + 1),
            same_line=False)

        uid_data: dict = get_firmware_uid_data(
                uid=uid['uid'], config_db=fact_config_data['common']['postgres'], get_fw_file_data=True)

        export_list.append(uid_data['summary'])

    # Save UIDs as CSV file.
    file_path = directory_path + os.sep + 'uids.csv'
    csvs.write_list_to_csv(export_list, file_path)

    return None

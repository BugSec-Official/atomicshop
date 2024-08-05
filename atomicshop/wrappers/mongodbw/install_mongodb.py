import os
import requests
from typing import Union

from ... import urls, web, permissions, get_process_list, filesystem
from ...print_api import print_api
from .. import msiw


MONGODB_DOWNLOAD_PAGE_URL: str = 'https://www.mongodb.com/try/download/community'
WHERE_TO_SEARCH_FOR_MONGODB_EXE: str = 'C:\\Program Files\\MongoDB\\Server\\'
MONGODB_EXE_NAME: str = 'mongod.exe'


class MongoDBWebPageNoSuccessCodeError(Exception):
    pass


class MongoDBNoDownloadLinksError(Exception):
    pass


class MongoDBNoDownloadLinkForWindowsError(Exception):
    pass


class MongoDBInstallationError(Exception):
    pass


def get_latest_mongodb_download_url(
        no_rc_version: bool = True,
        major_specific: int = None
):
    response = requests.get(MONGODB_DOWNLOAD_PAGE_URL)

    if response.status_code != 200:
        raise MongoDBWebPageNoSuccessCodeError("Failed to load the download page.")

    urls_in_page: list = urls.find_urls_in_text(response.text)
    if not urls_in_page:
        raise MongoDBNoDownloadLinksError("Could not find the download link for MongoDB Community Server.")

    windows_urls: list = []
    for url in urls_in_page:
        if 'windows' in url and 'x86_64' in url and url.endswith('.msi'):
            if no_rc_version and '-rc' in url:
                continue
            windows_urls.append(url)

    if major_specific:
        for url in windows_urls:
            if f'-{major_specific}.' in url:
                windows_urls = [url]
                break

    if not windows_urls:
        raise MongoDBNoDownloadLinkForWindowsError(
            "Could not find the download link for MongoDB Community Server for Windows x86_64.")

    # Return the latest URL only.
    return windows_urls[0]


def is_service_running() -> bool:
    """
    Check if the MongoDB service is running.
    :return: bool, True if the MongoDB service is running, False otherwise.
    """
    current_processes: dict = (
        get_process_list.GetProcessList(get_method='pywin32', connect_on_init=True).get_processes())

    for pid, process_info in current_processes.items():
        if MONGODB_EXE_NAME in process_info['name']:
            return True

    return False


def is_installed() -> Union[str, None]:
    """
    Check if MongoDB is installed.
    :return: string if MongoDB executable is found, None otherwise.
    """

    return filesystem.find_file(MONGODB_EXE_NAME, WHERE_TO_SEARCH_FOR_MONGODB_EXE)


def download_install_latest_main(
        no_rc_version: bool = True,
        major_specific: int = None,
        force: bool = False
):
    """
    Download and install the latest version of MongoDB Community Server.
    :param no_rc_version: bool, if True, the latest non-RC version will be downloaded.
    :param major_specific: int, if set, the latest version of the specified major version will be downloaded.
    :param force: bool, if True, MongoDB will be installed even if it is already installed.
    :return:
    """

    if not permissions.is_admin():
        print_api("This function requires administrator privileges.", color='red')
        return 1

    if is_service_running():
        print_api("MongoDB service is running - already installed.", color='blue')

        if not force:
            return 0
    else:
        print_api("MongoDB is service is not running.")

        mongo_is_installed: Union[str, None] = is_installed()
        if is_installed():
            message = f"MongoDB is installed in: {mongo_is_installed}\n" \
                      f"The service is not running. Fix the service or use the 'force' parameter to reinstall."
            print_api(message, color='yellow')

            if not force:
                return 0

    print_api("Fetching the latest MongoDB download URL...")
    mongo_installer_url = get_latest_mongodb_download_url(no_rc_version=no_rc_version, major_specific=major_specific)

    print_api(f"Downloading MongoDB installer from: {mongo_installer_url}")
    installer_file_path: str = web.download(mongo_installer_url)

    print_api("Installing MongoDB...")
    try:
        msiw.install_msi(
            installer_file_path,
            silent_no_gui=True,
            no_restart=True,
            terminate_required_processes=True,
            create_log_near_msi=True,
            scan_log_for_errors=True,
            additional_args='ADDLOCAL="ServerService"'
        )
    except msiw.MsiInstallationError as e:
        print_api(f'{e} Exiting...', color='red')
        return 1

    # Check if MongoDB is installed.
    message: str = ''
    mongo_is_installed = is_installed()
    if not mongo_is_installed:
        message += "MongoDB Executable not found.\n"

    if not is_service_running():
        message += "MongoDB service is not running.\n"

    if message:
        message += f"MSI Path: {installer_file_path}"
        print_api(message, color='red')
        return 1
    else:
        success_message: str = f"MongoDB installed successfully to: {mongo_is_installed}\n" \
                               f"Service is running."
        print_api(success_message, color='green')

    # Clean up the installer file
    if os.path.exists(installer_file_path):
        os.remove(installer_file_path)
        print_api("Cleaned up the installer file.")

    return 0

import os
import requests
from typing import Union
import argparse
import subprocess

from ... import urls, web
from ...permissions import permissions
from ...print_api import print_api
from .. import msiw
from . import mongo_infra


MONGODB_DOWNLOAD_PAGE_URL: str = 'https://www.mongodb.com/try/download/community'
COMPASS_INSTALLATION_SCRIPT_URL: str = \
    'https://raw.githubusercontent.com/mongodb/mongo/master/src/mongo/installer/compass/Install-Compass.ps1'


class MongoDBWebPageNoSuccessCodeError(Exception):
    pass


class MongoDBNoDownloadLinksError(Exception):
    pass


class MongoDBNoDownloadLinkForWindowsError(Exception):
    pass


class MongoDBInstallationError(Exception):
    pass


def get_latest_mongodb_download_url(
        rc_version: bool = True,
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
            if not rc_version and '-rc' in url:
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


def parse_args():
    parser = argparse.ArgumentParser(description='Install MongoDB Community Server.')
    # Mutually exclusive group for 'ir' and 'er'
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '-er', '--exclude-rc',
        action='store_true',
        help='Install latest version, but exclude release candidate versions.'
    )
    group.add_argument(
        '-ir', '--include-rc',
        action='store_true',
        help='Install the latest version of MongoDB including release candidates.'
    )

    # Optional arguments
    parser.add_argument(
        '-c', '--compass',
        action='store_true',
        help='Install MongoDB Compass.'
    )
    parser.add_argument(
        '-m', '--major',
        type=int,
        help='Download the latest version of the specified major version.'
    )
    parser.add_argument(
        '-f', '--force',
        action='store_true',
        help='Force the installation even if MongoDB is already installed.'
    )

    args = parser.parse_args()

    # Validation logic: At least one of '-nr', '-ir', or '-c' must be provided
    if not (args.no_rc or args.include_rc or args.compass):
        parser.error("At least one of '-nr', '-ir', or '-c' must be specified.")

    return args


def download_install_process(
        rc_version: bool = False,
        no_rc_version: bool = True,
        major_specific: int = None,
        compass: bool = False,
        force: bool = False
) -> int:
    """
    Download and install the latest version of MongoDB Community Server.

    :param rc_version: bool, if True, the latest RC version will be downloaded.
    :param no_rc_version: bool, if True, the latest non-RC version will be downloaded.
    :param major_specific: int, if set, the latest version of the specified major version will be downloaded.
    :param compass: bool, if True, MongoDB Compass will be installed.
    :param force: bool, if True, MongoDB will be installed even if it is already installed.
    :return: int, 0 if successful, 1 if failed.
    """

    if not permissions.is_admin():
        print_api("This function requires administrator privileges.", color='red')
        return 1

    if rc_version and no_rc_version:
        print_api("Both 'rc_version' and 'no_rc_version' cannot be True at the same time.", color='red')
        return 1

    if not (rc_version or no_rc_version) and not compass:
        print_api("At least one of 'rc_version', 'no_rc_version', or 'compass' must be True.", color='red')
        return 1

    # If we need to install mongo db.
    if rc_version or no_rc_version:
        if rc_version:
            download_rc_version: bool = True
        elif no_rc_version:
            download_rc_version: bool = False
        else:
            raise ValueError("Invalid value for 'rc_version' and 'no_rc_version'.")

        if mongo_infra.is_service_running():
            print_api("MongoDB service is running - already installed. Use [-f] to reinstall.", color='blue')

            if not force:
                return 0
        else:
            print_api("MongoDB is service is not running.")

            mongo_is_installed: Union[str, None] = mongo_infra.is_installed()
            if mongo_infra.is_installed():
                message = f"MongoDB is installed in: {mongo_is_installed}\n" \
                          f"The service is not running. Fix the service or use the 'force' parameter to reinstall."
                print_api(message, color='yellow')

                if not force:
                    return 0

        print_api("Fetching the latest MongoDB download URL...")
        mongo_installer_url = get_latest_mongodb_download_url(rc_version=download_rc_version, major_specific=major_specific)

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
        mongo_is_installed = mongo_infra.is_installed()
        if not mongo_is_installed:
            message += "MongoDB Executable not found.\n"

        if not mongo_infra.is_service_running():
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

    if not compass:
        return 0

    # It doesn't matter what you do with the MSI it will not install Compass, only if you run it manually.
    # So we will use installation script from their GitHub.
    print_api("Downloading MongoDB Compass installation script...")
    compass_script_path: str = web.download(COMPASS_INSTALLATION_SCRIPT_URL)

    print_api("Installing MongoDB Compass from script...")
    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", compass_script_path])

    # Clean up the installer file
    if os.path.exists(compass_script_path):
        os.remove(compass_script_path)
        print_api("Cleaned up the Compass installer file.")

    return 0


def download_install_latest_main() -> int:
    """
    Download and install the latest version of MongoDB Community Server.

    :return: int, 0 if successful, 1 if failed.
    """

    args = parse_args()

    return download_install_process(
        rc_version=args.include_rc,
        no_rc_version=args.exclude_rc,
        major_specific=args.major,
        compass=args.compass,
        force=args.force
    )

import os
import subprocess
import requests

from ... import urls, web
from ...print_api import print_api


MONGODB_DOWNLOAD_PAGE_URL: str = 'https://www.mongodb.com/try/download/community'


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

    if not windows_urls:
        raise MongoDBNoDownloadLinkForWindowsError(
            "Could not find the download link for MongoDB Community Server for Windows x86_64.")

    # Return the latest URL only.
    return windows_urls[0]


def install_mongodb(installer_path):
    try:
        subprocess.run([installer_path, '/install', '/quiet', '/norestart'], check=True)
        print_api("MongoDB installation completed successfully.", color='green')
    except subprocess.CalledProcessError as e:
        raise MongoDBInstallationError(
            f"An error occurred during the installation: {e}\n"
            f"Try running manually: {installer_path}")


def is_installed() -> bool:
    """
    Check if MongoDB is installed.
    :return: bool, True if MongoDB is installed, False otherwise.
    """
    try:
        # Run the 'mongo' command to see if MongoDB is installed
        result = subprocess.run(['mongo', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Check the return code
        if result.returncode == 0:
            return True
        else:
            return False
    except FileNotFoundError:
        return False


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

    if is_installed():
        print_api("MongoDB is already installed.", color='blue')

        if not force:
            return 0

    print_api("Fetching the latest MongoDB download URL...")
    mongo_installer_url = get_latest_mongodb_download_url(no_rc_version=no_rc_version, major_specific=major_specific)

    print_api(f"Downloading MongoDB installer from: {mongo_installer_url}")
    installer_file_path: str = web.download(mongo_installer_url)

    print_api("Installing MongoDB...")
    install_mongodb(installer_file_path)

    # Clean up the installer file
    if os.path.exists(installer_file_path):
        os.remove(installer_file_path)
        print_api("Cleaned up the installer file.")

    return 0

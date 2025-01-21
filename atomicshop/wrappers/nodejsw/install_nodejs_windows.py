import os
import requests
import time
import tempfile

from ... import web
from ...permissions import permissions
from .. import msiw
from ...print_api import print_api


WINDOWS_X64_SUFFIX: str = "x64.msi"


class NodeJSWindowsInstallerNoVersionsFound(Exception):
    pass


class NodeJSWindowsInstallerMoreThanOneVersionFound(Exception):
    pass


class NodeJSWindowsInstallerFailedToExtractFileNameFromString(Exception):
    pass


class NodeJSWindowsInstallerFailedToExtractVersionInString(Exception):
    pass


def get_latest_nodejs_version():
    """
    Fetch the latest Node.js version from the official Node.js website.
    """
    print_api("Fetching the latest Node.js version...")
    url = "https://nodejs.org/dist/latest/SHASUMS256.txt"

    response = requests.get(url, timeout=10)
    response.raise_for_status()
    # Parse the file for the Node.js version
    found_versions: list = []
    for line in response.text.splitlines():
        if line.endswith(WINDOWS_X64_SUFFIX):
            found_versions.append(line)

    if not found_versions:
        raise NodeJSWindowsInstallerNoVersionsFound("No Node.js versions found in [https://nodejs.org/dist/latest/SHASUMS256.txt]")
    elif len(found_versions) > 1:
        raise NodeJSWindowsInstallerMoreThanOneVersionFound(f"More than one Node.js version found:\n"
                                                            f"{'\n'.join(found_versions)}")

    try:
        file_name = found_versions[0].split("  ")[-1]
    except IndexError:
        raise NodeJSWindowsInstallerFailedToExtractFileNameFromString("Failed to extract the file name from the string.")

    try:
        version = file_name.replace("node-v", "").replace(f"-{WINDOWS_X64_SUFFIX}", "")
    except Exception:
        raise NodeJSWindowsInstallerFailedToExtractVersionInString("Failed to extract the version from the string.")

    print_api(f"Latest Node.js version: {version}")
    return version


def download_nodejs_installer(version):
    """
    Download the Node.js MSI installer for Windows.
    """

    version = f"v{version}"
    nodejs_base_url = f"https://nodejs.org/dist/{version}/"
    file_name = f"node-{version}-x64.msi"
    download_url = nodejs_base_url + file_name
    print_api(f"Downloading Node.js installer from: {download_url}")

    # Make temporary directory to store the installer
    temp_dir = tempfile.gettempdir()
    temp_file_path = web.download(download_url, temp_dir)
    return temp_file_path


def clean_up(installer_path):
    """
    Remove the installer file after installation.
    """
    try:
        if os.path.exists(installer_path):
            os.remove(installer_path)
            print_api(f"Removed installer: {installer_path}")
    except Exception as e:
        print_api(f"Failed to clean up the installer: {e}")


def install_nodejs_windows() -> int:
    if not permissions.is_admin():
        print_api("This script requires administrative privileges to install Node.js.")
        return 1

    print_api("Starting Node.js installation process...")
    version = get_latest_nodejs_version()
    if not version:
        print_api("Exiting: Could not fetch the latest Node.js version.")
        return 1

    installer_path = download_nodejs_installer(version)
    if not installer_path:
        print_api("Exiting: Failed to download the Node.js installer.")
        return 1

    msiw.install_msi(installer_path, silent_progress_bar=True)
    time.sleep(5)  # Wait a few seconds for the installation to complete
    clean_up(installer_path)
    print_api("Installation process finished.")
    return 0
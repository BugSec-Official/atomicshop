import requests
from bs4 import BeautifulSoup
import subprocess

from ... import web, filesystem
from ...print_api import print_api


# URL to the PyCharm Community Edition download page
PYCHARM_DOWNLOAD_URL = 'https://www.jetbrains.com/pycharm/download/#section=windowsC'


def download_install_main():
    """
    Main function to download and install the latest PyCharm Community Edition.

    Usage:
    python -m atomicshop.mains.installs.pycharm

    Or run the main function directly.
        from atomicshop.wrappers import pycharmw


        def main():
            pycharmw.download_install_main()


        if __name__ == "__main__":
            main()
    """

    def get_latest_pycharm_download_link():
        url = "https://www.jetbrains.com/pycharm/download/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise Exception("Failed to load the download page")

        soup = BeautifulSoup(response.text, 'html.parser')
        download_link = None

        # Find the Professional version download link
        for a in soup.find_all('a', href=True):
            if '/download?code=PCC&platform=windows' in a['href']:
                download_link = a['href']
                break

        if not download_link:
            raise Exception("Could not find the download link for the latest version of PyCharm Professional")

        return f"https:{download_link}"

    installer_path: str = None
    try:
        print_api("Fetching the latest PyCharm download link...")
        download_url = get_latest_pycharm_download_link()
        print_api(f"Download URL: {download_url}")

        print_api("Starting the download...")
        file_name = "pycharm-latest.exe"
        # download_file(download_url, file_name)
        installer_path = web.download(file_url=download_url, file_name=file_name)
        print_api(f"Downloaded the latest version of PyCharm to {file_name}", color='green')
    except Exception as e:
        print_api(f"An error occurred: {e}")

    if not installer_path:
        print_api("Failed to download the latest version of PyCharm", color='red')
        return 1

    # Install PyCharm
    # Run the installer
    print_api("Running the installer...")
    subprocess.run([installer_path, '/S'], check=True)  # /S for silent installation
    print_api("Installation complete.", color='green')

    # Remove the installer
    filesystem.remove_file(installer_path)

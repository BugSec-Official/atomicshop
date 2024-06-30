import requests
import os
import subprocess
import tempfile


# URL to the PyCharm Community Edition download page
PYCHARM_DOWNLOAD_URL = 'https://www.jetbrains.com/pycharm/download/download-thanks.html?platform=windows&code=PCC'


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

    # Get the redirect URL for the download
    response = requests.get(PYCHARM_DOWNLOAD_URL, allow_redirects=True)

    # Extract the final download URL
    download_url = response.url

    # Get the file name from the download URL
    file_name = download_url.split('/')[-1]

    # Create a temporary directory to download the installer
    temp_dir = tempfile.mkdtemp()
    installer_path = os.path.join(temp_dir, file_name)

    # Download the installer
    print(f"Downloading {file_name}...")
    with requests.get(download_url, stream=True) as r:
        r.raise_for_status()
        with open(installer_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    print("Download complete.")

    # Install PyCharm
    # Run the installer
    print("Running the installer...")
    subprocess.run([installer_path, '/S'], check=True)  # /S for silent installation
    print("Installation complete.")

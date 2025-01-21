import sys
import subprocess
import tempfile

from atomicshop.print_api import print_api
from atomicshop.wrappers import githubw
from atomicshop.permissions import permissions
from atomicshop.wrappers.nodejsw import install_nodejs_windows


WINDOWS_TESSERACT_DEFAULT_INSTALLATION_DIRECTORY: str = r"C:\Program Files\Tesseract-OCR"


def main():
    if not permissions.is_admin():
        print_api("Please run this script as an Administrator.", color="red")
        return 1

    if not install_nodejs_windows.is_nodejs_installed():
        install_nodejs_windows.install_nodejs_windows()
    install_nodejs_windows.add_nodejs_to_path()
    if not install_nodejs_windows.is_nodejs_installed():
        print_api("Node.js installation failed.")
        return 1

    print_api("PIP Installing Robocorp.")
    subprocess.check_call(["pip", "install", "--upgrade", "rpaframework"])

    print_api("PIP Installing Robocorp-Browser.")
    subprocess.check_call(["pip", "install", "--upgrade", "robotframework-browser"])

    print_api("PIP Installing Robocorp-Recognition.")
    subprocess.check_call(["pip", "install", "--upgrade", "rpaframework-recognition"])

    print_api("Installing Playwright browsers.")
    subprocess.check_call(["playwright", "install"])

    print_api("Initializing Robocorp Browser.")
    subprocess.check_call(["rfbrowser", "init"])

    print_api("Installing Tesseract OCR.")
    github_wrapper = githubw.GitHubWrapper(
        user_name="tesseract-ocr",
        repo_name="tesseract",
        branch="main")
    github_wrapper.build_links_from_user_and_repo()
    temp_file_path: str = tempfile.gettempdir()
    tesseract_installer = github_wrapper.download_latest_release(
        target_directory=temp_file_path,
        string_pattern="*tesseract*exe")

    # The Admin needed to install Tesseract.
    subprocess.check_call([tesseract_installer, "/S"])

    # Add Tesseract to the PATH.
    subprocess.check_call(["setx", "PATH", f"%PATH%;{WINDOWS_TESSERACT_DEFAULT_INSTALLATION_DIRECTORY}"])


if __name__ == '__main__':
    sys.exit(main())
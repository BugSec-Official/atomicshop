import subprocess
import sys
import os


from ... import print_api, web
from .. import ubuntu_terminal
from ...permissions import ubuntu_permissions


COMPASS_INSTALLATION_SCRIPT_URL: str = \
    'https://raw.githubusercontent.com/mongodb/mongo/master/src/mongo/installer/compass/install_compass'


def run_command(command):
    """Run a system command and exit if the command fails."""
    try:
        subprocess.run(command, check=True, shell=True)
    except subprocess.CalledProcessError as e:
        print_api.print_api(f"Error: {e}", color='red')
        sys.exit(1)


def install_mongodb(version):
    """Install the specified major version of MongoDB on Ubuntu."""

    if not version.endswith(".0"):
        version = f"{version}.0"

    print_api.print_api(f"Installing MongoDB {version} on Ubuntu...")
    print_api.print_api(f"Installing Prerequisites...")
    ubuntu_terminal.update_system_packages()
    ubuntu_terminal.install_packages(["wget", "curl", "gnupg"])

    # Step 1: Import the MongoDB public GPG key
    print_api.print_api("Step 1: Importing the MongoDB public GPG key...")
    run_command(f"curl -fsSL https://pgp.mongodb.com/server-{version}.asc | "
                f"sudo gpg --dearmor --yes -o /usr/share/keyrings/mongodb-server-{version}.gpg")

    # Step 2: Create the MongoDB list file for APT
    print_api.print_api("Step 2: Creating MongoDB APT list file...")
    distro_version = subprocess.check_output("lsb_release -sc", shell=True).decode('utf-8').strip()
    run_command(
        f"echo 'deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-{version}.gpg ] "
        f"https://repo.mongodb.org/apt/ubuntu {distro_version}/mongodb-org/{version} multiverse' | "
        f"sudo tee /etc/apt/sources.list.d/mongodb-org-{version}.list")

    # Step 3: Update the APT package index
    print_api.print_api("Step 3: Updating the APT package index...")
    ubuntu_terminal.update_system_packages()

    # Step 4: Install the latest version of MongoDB for the specified major version
    print_api.print_api(f"Step 4: Installing MongoDB version {version}...")
    ubuntu_terminal.install_packages(["mongodb-org"])

    # Step 5: Start MongoDB service and enable it on startup
    print_api.print_api("Step 5: Starting MongoDB service and enabling it on startup...")
    ubuntu_terminal.start_enable_service_check_availability("mongod")

    print_api.print_api(f"MongoDB {version} installation complete!", color='green')


def install_main(
        compass: bool = False,
):
    """
    Install the latest minor version of MongoDB Community Server on Ubuntu by providing the major version.
    :param compass: bool, if True, MongoDB Compass will be installed.
    :return:
    """
    # Ensure the user provides a MongoDB major version as an argument.
    if len(sys.argv) != 2:
        message: str = ("Usage: python install_mongodb.py <mongo_major_version>\n"
                        "Example: python install_mongodb.py 8")
        print_api.print_api(message, color='red')
        return 1

    mongo_version = sys.argv[1]

    # Call the 'install' function with the major version.
    install_mongodb(mongo_version)

    if not compass:
        return 0

    # It doesn't matter what you do with the MSI it will not install Compass, only if you run it manually.
    # So we will use installation script from their GitHub.
    print_api.print_api("Downloading MongoDB Compass installation script...")
    compass_script_path: str = web.download(COMPASS_INSTALLATION_SCRIPT_URL)

    print_api.print_api("Installing MongoDB Compass from script...")
    ubuntu_permissions.set_executable(compass_script_path)
    run_command(f'sudo -E python3 {compass_script_path}')

    # Clean up the installer file
    if os.path.exists(compass_script_path):
        os.remove(compass_script_path)
        print_api.print_api("Cleaned up the Compass installer file.")

    return 0

import os
import sys
from pathlib import Path

from ..import process, permissions
from ..print_api import print_api


def is_installed():
    # Command to check the status of the WSL feature
    command = "Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux"

    # Check if WSL is enabled
    if "Enabled" in process.run_powershell_command(command):
        return True
    else:
        return False


def is_ubuntu_installed() -> bool:
    """
    Check if Ubuntu is installed on WSL.
    :return: bool, True if Ubuntu is installed, False otherwise.
    """

    # Command to list installed WSL distributions
    command = "wsl --list --quiet"

    is_ubuntu_exists: bool = False
    # Check each distribution for being Ubuntu 22.04
    for distro in process.run_powershell_command(command):
        if "ubuntu" in distro.lower():
            is_ubuntu_exists = True
            break

    return is_ubuntu_exists


def is_ubuntu_version_installed(version: str = "22.04") -> bool:
    """
    Check if specific version of Ubuntu is installed on WSL.
    :param version: string, Ubuntu version to check for. Default is 22.04.
    :return: bool, True if Ubuntu is installed, False otherwise.
    """

    # Command to get Ubuntu version
    command = f"wsl -d Ubuntu lsb_release -a"

    # Execute the command
    result = process.execute_with_live_output(command)

    is_version_installed: bool = False
    # Parse the output for the version number
    for line in result:
        if "Release" in line and version in line:
            is_version_installed = True
            break

    return is_version_installed


def install_wsl(directory_path: str, enable_virtual_machine_platform: bool = True, set_default_version_2: bool = True):
    """
    Install WSL on Windows 10.
    :param directory_path: string, directory path to save Ubuntu package.
    :param enable_virtual_machine_platform: bool, True to enable Virtual Machine Platform feature.
    :param set_default_version_2: bool, True to set WSL version 2 as default.
    """

    # Check for admin privileges
    if not permissions.is_admin():
        sys.exit("Script must be run as administrator")

    # Check if WSL is already installed
    if is_installed():
        print_api("WSL is already installed", color='green')
    else:
        # Enable WSL
        print_api("Enabling Windows Subsystem for Linux...")
        process.run_powershell_command(
            "Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux")

        # Check if the system needs a reboot
        if "You must restart your computer" in process.run_powershell_command(
                "Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux"):
            print_api("Please restart your computer to complete the installation of WSL and rerun the script.")
            sys.exit(0)

    if enable_virtual_machine_platform:
        # Check if Hyper-V is enabled
        if "Enabled" in process.run_powershell_command(
                "Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V"):
            print_api("Hyper-V is enabled")
        else:
            # Command to enable Virtual Machine Platform
            command = "Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All"

            print_api("Enabling Virtual Machine Platform...")
            process.run_powershell_command(command)

    # Set WSL version 2 as default
    if set_default_version_2:
        print_api("Setting WSL version 2 as default...")
        process.execute_with_live_output("wsl --set-default-version 2")

    # Check if Ubuntu is already installed. If so, exit with a message.
    if is_ubuntu_version_installed():
        print_api("Ubuntu is already installed", color='green')
        sys.exit(0)

    # Download and Install Ubuntu
    print_api("Installing Ubuntu for WSL...")
    package_file_path: str = str(Path(directory_path, "Ubuntu.appx"))
    process.run_powershell_command(
        f"Invoke-WebRequest -Uri https://aka.ms/wslubuntu2204 -OutFile {package_file_path} -UseBasicParsing")
    process.run_powershell_command(f"Add-AppxPackage {package_file_path}")

    print_api("Ubuntu installation is complete. You can now launch Ubuntu from the Start Menu.")

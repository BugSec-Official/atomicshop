import sys
from pathlib import Path

from ..import process, permissions, virtualization
from ..print_api import print_api


def is_installed():
    # Command to check the status of the WSL feature
    command = "Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux"

    # Check if WSL is enabled
    if "Enabled" in process.run_powershell_command(command):
        return True
    else:
        return False


def get_installed_distros() -> list:
    """
    Get a list of installed WSL distros.
    :return: list, list of installed WSL distros.
    """
    return process.execute_with_live_output("wsl --list --quiet")


def get_available_distros_to_install() -> list:
    """
    Get a list of available WSL distros to install.
    :return: list, list of available WSL distros to install.
    """
    return process.execute_with_live_output("wsl --list --online")


def is_ubuntu_installed(version: str = "22.04") -> bool:
    """
    Check if specific version of Ubuntu is installed on WSL.
    :param version: string, Ubuntu version to check for. Default is 22.04.
    :return: bool, True if Ubuntu is installed, False otherwise.
    """

    if not version:
        version = str()

    installed_distros_list = get_installed_distros()

    if f'Ubuntu-{version}' in installed_distros_list:
        return True
    elif 'Ubuntu' in installed_distros_list:
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
    else:
        return False


def install_wsl_manual(
        directory_path: str, enable_virtual_machine_platform: bool = True, set_default_version_2: bool = True):
    # noinspection GrazieInspection
    """
        Install WSL on Windows 10.
        :param directory_path: string, directory path to save Ubuntu package.
        :param enable_virtual_machine_platform: bool, True to enable Virtual Machine Platform feature.
        :param set_default_version_2: bool, True to set WSL version 2 as default.

        Main.py example:
            import sys
            from atomicshop.wrappers import wslw


            def main():
                if len(sys.argv) < 2:
                    print("Usage: python main.py <directory_path_to_save_Ubuntu_package>")
                    sys.exit(1)

                wslw.install_wsl(directory_path=sys.argv[1])


            if __name__ == '__main__':
                main()
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
            "Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -NoRestart")

        # # Check if the system needs a reboot
        # if "RestartNeeded : True" in process.run_powershell_command(
        #         "Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux"):
        #     print_api("Please restart your computer to complete the installation of WSL and rerun the script.")
        #     sys.exit(0)

    # Enable Virtual Machine Platform is needed for WSL 2.
    if enable_virtual_machine_platform:
        # Check if Hyper-V is enabled
        if "Enabled" in process.run_powershell_command(
                "Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V"):
            print_api("Hyper-V is enabled")
        else:
            # Command to enable Virtual Machine Platform
            command = "Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All -NoRestart"

            print_api("Enabling Virtual Machine Platform...")
            process.run_powershell_command(command)

    # Set WSL version 2 as default.
    if set_default_version_2:
        print_api("Setting WSL version 2 as default...")
        process.execute_with_live_output("wsl --set-default-version 2")

    # Check if Ubuntu is already installed. If so, exit with a message.
    if is_ubuntu_installed():
        print_api("Ubuntu is already installed", color='green')
        sys.exit(0)

    # Before you install Ubuntu, you need to set the WSL to version 2.
    # You can do it after you install, but if so, you will need to set the Ubuntu to version 2 either.
    # Download and Install Ubuntu.
    print_api("Installing Ubuntu for WSL...")
    package_file_path: str = str(Path(directory_path, "Ubuntu.appx"))
    process.run_powershell_command(
        f"Invoke-WebRequest -Uri https://aka.ms/wslubuntu2204 -OutFile {package_file_path} -UseBasicParsing")
    process.run_powershell_command(f"Add-AppxPackage {package_file_path}")

    print_api("Ubuntu installation is complete. You can now launch Ubuntu from the Start Menu.")
    print_api("Please restart your computer to complete the installation.")


def install_wsl(distro: str = "Ubuntu-22.04"):
    # noinspection GrazieInspection
    """
        Install WSL and Ubuntu.
        :param distro: string, distro to install. Default is Ubuntu-22.04.
        :return:

        Main.py example:
            from atomicshop.wrappers import wslw


            def main():
                wslw.install_wsl()


            if __name__ == '__main__':
                main()
        """

    # Check for admin privileges
    if not permissions.is_admin():
        print_api("Script must be run as administrator", color='red')
        sys.exit(1)

    # Check if virtualization is enabled.
    if not virtualization.is_enabled():
        print_api("Virtualization is not enabled in the bios. Please enable it and rerun the script.", color='red')
        sys.exit(1)

    # Check if WSL and Ubuntu is already installed
    wsl_installed: bool = is_installed()
    ubuntu_installed: bool = is_ubuntu_installed()

    if wsl_installed and ubuntu_installed:
        print_api("WSL and Ubuntu is already installed", color='green')
        sys.exit(0)
    elif wsl_installed and not ubuntu_installed:
        print_api("WSL is already installed, installing Ubuntu")
    elif not wsl_installed:
        print_api("WSL is not installed, installing WSL and Ubuntu")

    command = f"wsl --install -d {distro}"
    process.execute_with_live_output(command)

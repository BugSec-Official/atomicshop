import subprocess
from pathlib import Path

from dkarchiver.arch_wrappers import zips
from dkinst.installers.helpers import docker_installer

from .... import filesystem
from ....permissions import ubuntu_permissions
from ....print_api import print_api
from ... import githubw, pipw, ubuntu_terminal
from .. import config_install


def install_before_restart(
        installation_directory: str,
        remove_existing_installation_directory: bool = True,
        fact_source_archive_path: str = None,
        use_built_in_fact_installer: bool = True,
        print_kwargs: dict = None
) -> int:
    """
    This function will install the FACT_core before the restart of the computer.
    :param installation_directory: string, the directory to install the FACT_core to.
    :param remove_existing_installation_directory: bool,
        if True, the existing installation directory will be removed.
        if False, the existing installation directory will not be removed and FACT installation scripts will do their
            best to install the FACT_core to the existing installation directory.
    :param fact_source_archive_path: string, the path to the FACT_core source archive.
        This is used when the FACT_core source archive is already downloaded, and you want to use the specific archive
        instead of downloading it again. Or you want to use a specific version of the FACT_core.
        This is optional, if not provided, the latest version of the FACT_core will be downloaded.
        The archive should be an exact copy of the FACT_core repository of the master branch as you download it from
        GitHub.
    :param use_built_in_fact_installer: bool, if True, the built-in FACT_core installer will be used.
        If False, only the regular prerequisites will be installed, while the user will need to install DOCKER
        and Node.js separately.
    :param print_kwargs: dict, the print kwargs for the print_api function.
    :return: int, 0 if the installation was successful, 1 if there was an error.
    """

    # if not permissions.is_admin():
    #     print_api("This script requires root privileges...", color='red')
    #     return 1

    # # Install docker in rootless mode.
    # with ubuntu_permissions.temporary_regular_permissions():
    #     install_docker.install_docker_ubuntu(
    #         use_docker_installer=True, rootless=True, add_current_user_to_docker_group_bool=False)

    # docker_keyring_file_path: str = "/etc/apt/keyrings/docker.gpg"
    # nodesource_keyring_file_path: str = "/etc/apt/keyrings/nodesource.gpg"
    fact_core_pre_install_file_path = str(Path(installation_directory, config_install.PRE_INSTALL_FILE_PATH))

    # Remove the existing keyrings, so we will not be asked to overwrite it if it exists.
    # filesystem.remove_file(docker_keyring_file_path)
    # filesystem.remove_file(nodesource_keyring_file_path)

    # Remove the existing installation directory.
    if remove_existing_installation_directory:
        filesystem.remove_directory(installation_directory)

    # Since you run the script with sudo, we need to change the permissions to the current user.
    # with ubuntu_permissions.temporary_regular_permissions():
    # Create the FACT_core directory.
    filesystem.create_directory(installation_directory)

    if not fact_source_archive_path:
        # Download the FACT_core repo.
        if not filesystem.get_paths_from_directory(installation_directory, get_file=True):
            git_wrapper = githubw.GitHubWrapper(repo_url=config_install.FACT_CORE_GITHUB_URL)
            git_wrapper.build_links_from_repo_url()
            git_wrapper.download_and_extract_branch(
                target_directory=installation_directory,
                archive_remove_first_directory=True)
    else:
        # Extract the archive and remove the first directory.
        zips.extract_archive_with_zipfile(
            archive_path=fact_source_archive_path, extract_directory=installation_directory,
            remove_first_directory=True, **(print_kwargs or {}))

    # Set the executable permission on the pre-installation file.
    ubuntu_permissions.set_executable(fact_core_pre_install_file_path)

    if use_built_in_fact_installer:
        # Run the shell script
        subprocess.run(['bash', fact_core_pre_install_file_path])

        # Install docker. FACT installs the docker, but there can be a problem with permissions, so we need to add
        # the user permissions to the docker group before restart.
        if not docker_installer.add_current_user_to_docker_group():
            print_api("Docker is installed, but the current user was not added to the docker group.", color='red')
            return 1
    else:
        message = ("You will need to install DOCKER and NODEJS separately.\n"
                   "This was done to enable Rootless docker install and install other version of NodeJS.")
        print_api(message, color='yellow')

        ubuntu_terminal.update_system_packages()
        ubuntu_terminal.install_packages(['python3-pip', 'git', 'libffi-dev', 'lsb-release'])

        prerequisites_file_path = str(Path(installation_directory, config_install.PRE_INSTALL_PREREQUISITES_FILE_PATH))
        pipw.install_packages_with_current_interpreter(
            prefer_binary=True,
            requirements_file_path=prerequisites_file_path)

        # Install docker in rootless mode.
        # install_docker.install_docker_ubuntu(
        #     use_docker_installer=True, rootless=True, add_current_user_to_docker_group_bool=False)

        # Install docker in regular mode.
        result: int = docker_installer.install_docker_ubuntu(
            use_docker_installer=True, rootless=False, add_current_user_to_docker_group_bool=True)
        if result != 0:
            print_api("Docker installation failed. Please install Docker manually.", color='red')
            return result

    print_api("FACT_core installation before restart is finished.", color='green')
    print_api("Please restart the computer to continue the installation.", color='red')

    return 0
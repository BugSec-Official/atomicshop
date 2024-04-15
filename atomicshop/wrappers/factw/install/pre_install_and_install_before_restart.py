import subprocess
from pathlib import Path
import sys

from .... import permissions, filesystem
from ....archiver import zips
from ....print_api import print_api
from ... import githubw
from ...dockerw import install_docker
from .. import config_install


def install_before_restart(
        installation_directory: str,
        remove_existing_installation_directory: bool = True,
        fact_source_archive_path: str = None,
        print_kwargs: dict = None
):
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
    :param print_kwargs: dict, the print kwargs for the print_api function.
    :return:
    """

    if not permissions.is_admin():
        print_api("This script requires root privileges...", color='red')
        sys.exit(1)

    docker_keyring_file_path: str = "/etc/apt/keyrings/docker.gpg"
    nodesource_keyring_file_path: str = "/etc/apt/keyrings/nodesource.gpg"
    fact_core_pre_install_file_path = str(Path(installation_directory, config_install.PRE_INSTALL_FILE_PATH))

    # Remove the existing keyrings, so we will not be asked to overwrite it if it exists.
    filesystem.remove_file(docker_keyring_file_path)
    filesystem.remove_file(nodesource_keyring_file_path)

    # Remove the existing installation directory.
    if remove_existing_installation_directory:
        filesystem.remove_directory(installation_directory)

    # Since you run the script with sudo, we need to change the permissions to the current user.
    with permissions.temporary_regular_permissions():
        # Create the FACT_core directory.
        filesystem.create_directory(installation_directory)

        if not fact_source_archive_path:
            # Download the FACT_core repo.
            if not filesystem.get_file_paths_from_directory(installation_directory):
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
        permissions.set_executable_permission(fact_core_pre_install_file_path)

    # Run the shell script
    subprocess.run(['bash', fact_core_pre_install_file_path])

    # Install docker. FACT installs the docker, but there can be a problem with permissions, so we need to add
    # the user permissions to the docker group before restart.
    if not install_docker.add_current_user_to_docker_group():
        print_api("Docker is installed, but the current user was not added to the docker group.", color='red')
        sys.exit(1)

    print_api("FACT_core installation before restart is finished.", color='green')
    print_api("Please restart the computer to continue the installation.", color='red')

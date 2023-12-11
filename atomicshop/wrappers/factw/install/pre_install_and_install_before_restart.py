import subprocess
from pathlib import Path

from .... import permissions, filesystem
from ... import githubw
from .. import config_install


def install_before_restart(installation_directory: str):
    """
    This function will install the FACT_core before the restart of the computer.
    :param installation_directory: string, the directory to install the FACT_core to.
    :return:
    """

    if not permissions.is_admin():
        print("This script requires root privileges. Please enter your password for sudo access.")
        permissions.run_as_root(['-v'])

    docker_keyring_file_path: str = "/etc/apt/keyrings/docker.gpg"
    fact_core_pre_install_file_path = str(Path(installation_directory, config_install.PRE_INSTALL_FILE_PATH))

    # Remove the docker keyring, so we will not be asked to overwrite it if it exists.
    filesystem.remove_file(docker_keyring_file_path)

    with permissions.temporary_regular_permissions():
        # Create the FACT_core directory.
        filesystem.create_directory(installation_directory)

        # Download the FACT_core repo.
        if not filesystem.get_file_paths_from_directory(installation_directory):
            git_wrapper = githubw.GitHubWrapper(repo_url=config_install.FACT_CORE_GITHUB_URL)
            git_wrapper.build_links_from_repo_url()
            git_wrapper.download_and_extract_branch(
                target_directory=installation_directory,
                archive_remove_first_directory=True)

    # Set the executable permission on the pre-install file.
    permissions.set_executable_permission(fact_core_pre_install_file_path)

    # Run the shell script
    subprocess.run(['bash', fact_core_pre_install_file_path])


import sys
import subprocess
import getpass

from ... import process, filesystem, permissions
from ...print_api import print_api
from .. import ubuntu_terminal


def is_docker_installed():
    """
    The function will check if docker is installed.
    :return: bool.
    """

    try:
        # Run the command 'docker --version'
        result = subprocess.run(['docker', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Check if the command was successful
        if result.returncode == 0:
            message = f"Docker is installed. Version: {result.stdout.strip()}"
            print_api(message, color='green')
            return True
        else:
            print_api("Docker is not installed.")
            return False
    except FileNotFoundError:
        print_api("Docker command not found. Docker is not installed.")
        return False


def add_current_user_to_docker_group(print_kwargs: dict = None):
    """
    The function will add the current user to the docker group.

    :param print_kwargs: dict, the print arguments.
    :return:
    """
    # Check if current user that executed the script is a sudo user. If not, use the current user.
    sudo_executer_username: str = permissions.get_ubuntu_sudo_executer_username()
    if sudo_executer_username:
        current_user = sudo_executer_username
    else:
        current_user = getpass.getuser()

    # Add the current user to the docker group.
    # subprocess.check_call(['sudo', 'usermod', '-aG', 'docker', current_user])
    command = f"sudo usermod -aG docker {current_user}"
    # Execute the command
    subprocess.run(command, shell=True, capture_output=True, text=True)

    # Check if the user was added to the docker group.
    result = subprocess.run(['groups', current_user], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if 'docker' in result.stdout:
        print_api(f"User {current_user} was added to the docker group.", color='green', **(print_kwargs or {}))
        return True
    else:
        print_api(f"User {current_user} was not added to the docker group. Try executing with sudo", color='red',
                  **(print_kwargs or {}))
        return False


def install_docker_ubuntu(
        use_docker_installer: bool = True,
        rootless: bool = False,
        add_current_user_to_docker_group_bool: bool = False
):
    """
    The function will install docker on ubuntu.
    Note: If you want to install docker in rootless mode, you need to run the script without sudo.

    :param rootless: bool, if True, the rootless installation will be performed.
        Meaning, you will be able to run the 'docker' command without sudo and you will not need to add the
        current user to the docker group.
    :param use_docker_installer: bool, if True, the docker installer will be used.
        If False, the docker will be installed using the apt package manager, custom repo and keyring.
    :param add_current_user_to_docker_group_bool: bool, if True, the current user will be added to the docker group.
        So the user will be able to run the 'docker' command without sudo. If you install docker in rootless mode
        this is not needed.

    Usage in main.py (run with sudo):
        from atomicshop.wrappers.dockerw import install_docker


        def main():
            install_docker.install_docker_ubuntu()


        if __name__ == '__main__':
            main()
    """

    if rootless and permissions.is_admin():
        print_api('Rootless installation requires running the script without sudo.', color='red')
        sys.exit()

    if use_docker_installer:
        if not ubuntu_terminal.is_executable_exists('curl'):
            print_api('curl is not installed, installing...', color='yellow')
            ubuntu_terminal.update_system_packages()
            ubuntu_terminal.install_packages(['curl'])

        # Use the docker installer script.
        # The script will install docker and add the current user to the docker group.
        # The script will also install docker-compose and docker-buildx.
        # process.execute_script('curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh', shell=True)
        process.execute_script('curl -fsSL https://get.docker.com | sh', shell=True)
        # process.execute_script('curl -fsSL https://get.docker.com -o get-docker.sh', shell=True)
        # process.execute_script('sh get-docker.sh', shell=True)
        # filesystem.remove_file('get-docker.sh')
    else:
        # Remove the existing keyrings, so we will not be asked to overwrite it if it exists.
        docker_keyring_file_path: str = "/etc/apt/keyrings/docker.gpg"
        filesystem.remove_file(docker_keyring_file_path)

        script = f"""
        # Step 1: Set up Docker's apt repository
        sudo apt-get update
        sudo apt-get install -y ca-certificates curl gnupg
        sudo install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        sudo chmod a+r /etc/apt/keyrings/docker.gpg
        
        # Add the repository to Apt sources
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        sudo apt-get update
        
        # Step 2: Install the Docker packages
        sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin docker-ce-rootless-extras
        
        # Step 3: Verify the installation
        # sudo docker run hello-world
        
        # Add Privileges to run docker without sudo. Add current user to Docker superuser group.
        # sudo usermod -aG docker $USER
        """

        process.execute_script(script, shell=True)

    if rootless:
        # Install uidmap package.
        if not ubuntu_terminal.is_package_installed('uidmap'):
            print_api('uidmap is not installed, installing...', color='yellow')
            ubuntu_terminal.update_system_packages()
            ubuntu_terminal.install_packages(['uidmap'])

        with permissions.temporary_regular_permissions():
            # After 'get-docker.sh' execution, we will install docker in rootless mode.
            # process.execute_script('dockerd-rootless-setuptool.sh install', shell=True, as_regular_user=True)
            process.execute_script(
                '/usr/bin/dockerd-rootless-setuptool.sh install',
                as_regular_user=True,
                shell=True,
                executable=None)

        # Start and enable the docker service in user mode.
        docker_start_command = ubuntu_terminal.get_command_execution_as_sudo_executer(
            'systemctl --user start docker.service')
        docker_enable_command = ubuntu_terminal.get_command_execution_as_sudo_executer(
            'systemctl --user enable docker.service')
        print_api('Starting and enabling the docker service in user mode...')
        process.execute_script(docker_start_command, shell=True, executable=None)
        process.execute_script(docker_enable_command, shell=True, executable=None)

        print_api('Executing "loginctl enable-linger" to enable Docker to run when the user is not logged in...')
        non_sudo_executer = permissions.get_ubuntu_sudo_executer_username()
        # Enable lingering so Docker runs when the user is not logged in
        process.execute_script(f'sudo loginctl enable-linger {non_sudo_executer}', shell=True)

        print_api('Adding $HOME/bin to your PATH...')
        # Add $HOME/bin to your PATH if it's not already there.
        with permissions.temporary_regular_permissions():
            ubuntu_terminal.add_path_to_bashrc(as_regular_user=True)

        # Add appropriate permissions to the docker socket, so the user can run docker commands without sudo in python.
        # with open('/etc/profile.d/docker_vars.sh', 'w') as file:
        #     file.write('export DOCKER_HOST=unix:///run/user/1000/docker.sock')

        # Since we are installing the rootless mode, this script runs without sudo, so to add the DOCKER_HOST variable
        # to the environment, we need to add it to the /etc/profile.d/docker_vars.sh file with sudo.
        command = "echo 'export DOCKER_HOST=unix:///run/user/1000/docker.sock' | sudo tee /etc/profile.d/docker_vars.sh"
        subprocess.run(command, shell=True, check=True)

        # ubuntu_terminal.add_line_to_bashrc(
        #     'export DOCKER_HOST=unix:///run/user/1000/docker.sock', as_regular_user=True)
        # process.execute_script('export DOCKER_HOST=unix:///run/user/1000/docker.sock', shell=True)
        # Restart shell.
        # process.execute_script('source ~/.bashrc', shell=True)

    if add_current_user_to_docker_group_bool:
        # Check if current user that executed the script is a sudo user. If not, use the current user.
        # Add the current user to the docker group.
        add_current_user_to_docker_group()

        # Verify the installation.
        result: list = process.execute_with_live_output('sudo docker run hello-world')
    else:
        result: list = process.execute_with_live_output('docker run hello-world')

    print_api('\n'.join(result))

    if 'Hello from Docker!' in '\n'.join(result):
        print_api('Docker installed successfully.', color='green')
        return True
    else:
        print_api('Docker installation failed.', color='red')
        print_api('Please check the logs above for more information.', color='red')
        return False

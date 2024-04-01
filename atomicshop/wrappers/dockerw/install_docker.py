import subprocess

from ... import process, filesystem
from ...print_api import print_api


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


def install_docker_ubuntu():
    """
    The function will install docker on ubuntu.

    Usage in main.py (run with sudo):
        from atomicshop.wrappers.dockerw import install_docker


        def main():
            install_docker.install_docker_ubuntu()


        if __name__ == '__main__':
            main()
    """

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
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # Step 3: Verify the installation
    # sudo docker run hello-world
    
    # Add Privileges to run docker without sudo. Add current user to Docker superuser group.
    sudo usermod -aG docker $USER
    """

    process.execute_script(script, shell=True)

    # Verify the installation.
    result: list = process.execute_with_live_output('sudo docker run hello-world')

    print_api('\n'.join(result))

    if 'Hello from Docker!' in '\n'.join(result):
        print_api('Docker installed successfully.', color='green')
        return True
    else:
        print_api('Docker installation failed.', color='red')
        print_api('Please check the logs above for more information.', color='red')
        return False

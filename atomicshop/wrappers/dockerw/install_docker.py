from ... import process


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

    """
    #!/bin/bash
    
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
    sudo docker run hello-world
    
    # Add Privileges to run docker without sudo. Add current user to Docker superuser group.
    # So you can use docker without sudo.
    sudo usermod -aG docker $USER
    """

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
    sudo docker run hello-world
    
    # Add Privileges to run docker without sudo. Add current user to Docker superuser group.
    sudo usermod -aG docker $USER
    """

    process.execute_script_ubuntu(script, shell=True)

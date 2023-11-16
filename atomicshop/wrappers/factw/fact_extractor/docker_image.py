from ....import process


def create_docker_image_ubuntu(directory_path: str):
    """
    This function creates a docker image using the Dockerfile in the given directory.
    The git repository will be downloaded there and the image will be created.

    :param directory_path: string, path to the directory where download the fact_extractor repo with the Dockerfile.
    :return:

    Usage in main.py (run with sudo):
        import sys
        from atomicshop.wrappers.factw.fact_extractor import docker_image


        def main():
            if len(sys.argv) < 2:
                print("Usage: python main.py <directory_path>")
                sys.exit(1)

            docker_image.create_docker_image_ubuntu(directory_path=sys.argv[1])


        if __name__ == '__main__':
            main()
    """

    """
    # batch commands explanations:
    #!/bin/bash

    # Run this script with sudo
    
    # If you get an error on excution use dos2unix to convert windows style file to linux.
    # -bash: ./install_fact_extractor_docker.sh: /bin/bash^M: bad interpreter: No such file or directory
    # sudo apt-get install dos2unix
    # dos2unix ./install_fact_extractor_docker.sh

    # Pull docker image from the repo.
    docker pull fkiecad/fact_extractor

    # Start from the directory you want the git repo to be downloaded.
    # Clone the repository
    git clone https://github.com/fkie-cad/fact_extractor.git

    # Navigate into the repository directory
    cd fact_extractor

    # Start docker service.
    sudo service docker start

    # Build the Docker image
    sudo docker build -t fact_extractor .
    """

    script = f"""
    docker pull fkiecad/fact_extractor
    cd "{directory_path}"
    git clone https://github.com/fkie-cad/fact_extractor.git
    cd fact_extractor
    sudo service docker start
    sudo docker build -t fact_extractor .
    """

    process.execute_script_ubuntu(script, shell=True)

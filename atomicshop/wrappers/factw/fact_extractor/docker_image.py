from ....import process
from ...dockerw import install_docker, dockerw


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

    # Check if docker is installed.
    if not install_docker.is_docker_installed():
        install_docker.install_docker_ubuntu()

    # Remove the image if exists.
    images = dockerw.get_images()
    for image in images:
        # There are 2 images:
        # 'fkiecad/fact_extractor:latest' - The image that is downloaded.
        # 'fact_extractor:latest' - The image that is built.
        test = image.tags
        for tag in image.tags:
            if 'fact_extractor' in tag:
                dockerw.remove_image(image_id_or_tag=image.id)

    # Create the script to execute.
    script = f"""
    #!/bin/bash

    # Run this script with sudo
    
    # If you get an error on execution use dos2unix to convert windows style file to linux.
    # -bash: ./install_fact_extractor_docker.sh: /bin/bash^M: bad interpreter: No such file or directory
    # sudo apt-get install dos2unix
    # dos2unix ./install_fact_extractor_docker.sh

    # Pull docker image from the repo.
    docker pull fkiecad/fact_extractor
    
    # Navigate to specified directory to download the repo and create the docker image.
    cd "{directory_path}"
    
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

    # Execute the script.
    process.execute_script(script, shell=True)

from ....import process


def create_docker_image_ubuntu(directory_path: str):
    """
    This function creates a docker image using the Dockerfile in the given directory.
    The git repository will be downloaded there and the image will be created.

    :param directory_path: string, path to the directory where download the fact_extractor repo with the Dockerfile.
    :return:

    Usage in main.py:
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

    script = f"""
    docker pull fkiecad/fact_extractor
    cd {directory_path}
    git clone https://github.com/fkie-cad/fact_extractor.git
    cd fact_extractor
    sudo service docker start
    sudo docker build -t fact_extractor .
    """
    process.execute_script_ubuntu(script, shell=True)

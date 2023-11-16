import sys
from atomicshop.wrappers.factw.fact_extractor import docker_image


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <directory_path>")
        sys.exit(1)

    docker_image.create_docker_image_ubuntu(directory_path=sys.argv[1])


if __name__ == '__main__':
    main()

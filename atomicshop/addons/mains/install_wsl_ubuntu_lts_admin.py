import sys
from atomicshop.wrappers import wslw


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <directory_path_to_save_Ubuntu_package>")
        sys.exit(1)

    wslw.install_wsl(directory_path=sys.argv[1])


if __name__ == '__main__':
    main()

import sys

from atomicshop.wrappers.nodejsw import install_nodejs_windows


def main():
    install_nodejs_windows.install_nodejs_windows()


if __name__ == "__main__":
    sys.exit(main())
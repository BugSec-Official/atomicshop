#! /usr/bin/env python3
import sys

from atomicshop.wrappers.nodejsw import install_nodejs_ubuntu


def main():
    install_nodejs_ubuntu.install_nodejs_main()


if __name__ == "__main__":
    sys.exit(main())

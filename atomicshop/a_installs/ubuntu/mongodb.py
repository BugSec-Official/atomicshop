#! /usr/bin/env python3
import sys

from atomicshop.wrappers.mongodbw import install_mongodb_ubuntu


def main():
    install_mongodb_ubuntu.install_main(compass=True)


if __name__ == "__main__":
    sys.exit(main())

#! /usr/bin/env python3
from atomicshop.wrappers.elasticsearchw import install_elastic


def main():
    install_elastic.install_elastic_kibana_ubuntu(install_elastic=True, install_kibana=True)


if __name__ == '__main__':
    main()

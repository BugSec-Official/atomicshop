#! /usr/bin/env python3
from atomicshop.wrappers.dockerw import install_docker


def main():
    install_docker.install_docker_ubuntu(
        use_docker_installer=True, rootless=False, add_current_user_to_docker_group_bool=True)


if __name__ == '__main__':
    main()

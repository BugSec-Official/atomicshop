import sys

from atomicshop.mitm.engines.create_module_template import CreateModuleTemplate


def main():
    CreateModuleTemplate()
    input('Press enter to exit...')
    return 0


if __name__ == '__main__':
    sys.exit(main())
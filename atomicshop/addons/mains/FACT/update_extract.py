import os

from atomicshop.wrappers.factw.fact_extractor import get_extractor
from atomicshop.wrappers.factw import config_install
from atomicshop import permissions, filesystem


def main():
    get_extractor.get_extractor_script()
    fact_extractor_executable_path: str = (
            filesystem.get_working_directory() + os.sep + config_install.FACT_EXTRACTOR_FILE_NAME)
    permissions.set_executable_permission(fact_extractor_executable_path)


if __name__ == '__main__':
    main()

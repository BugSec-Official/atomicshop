import os

FACT_CORE_GITHUB_URL: str = 'https://github.com/fkie-cad/FACT_core'

SRC_DIRECTORY_PATH: str = 'src'

# Before restart.
PRE_INSTALL_FILE_PATH: str = SRC_DIRECTORY_PATH + os.sep + 'install' + os.sep + 'pre_install.sh'

# After restart.
INSTALL_LOG_FILE_NAME: str = 'install.log'
INSTALL_FILE_PATH: str = SRC_DIRECTORY_PATH + os.sep + 'install.py'

FACT_EXTRACTOR_FILE_NAME: str = 'extract.py'

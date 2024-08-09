import sys

from atomicshop.wrappers.ctyping.msi_windows_installer import extract_msi_main


if __name__ == "__main__":
    sys.exit(extract_msi_main.extract_files_from_msi_main())

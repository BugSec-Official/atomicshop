import os
import sys
import argparse

from .base import msi
from . import base, tables, cabs
from ... import olefilew
from ....print_api import print_api
from ....archiver import sevenz_app_w


# Directory names.
EXTRACTED_FILES: str = "Extracted_MSI_Installation_Files"
EMBEDDED_FILES: str = "Embedded_MSI_Files"
CAB_FILES: str = "CAB_Files"
BINARY_FILES: str = "Binary_Files"
TABLE_CONTENTS: str = "Table_Contents"
ICON_FILES: str = "Icon_Files"
ISSETUPFILES: str = "ISSETUPFILES"
OLE_METADATA: str = "OLE_Metadata"
REGISTRY_CHANGES: str = "Registry_Changes"


def parse_args():
    parser = argparse.ArgumentParser(description="Extract files from the MSI file.")
    parser.add_argument("--msi_filepath", "-m", type=str, help="The path to the MSI file.")
    parser.add_argument("--output_directory", "-o", type=str, help="The main output directory.")
    parser.add_argument("--sevenz_path", "-s", type=str, help="The path to the 7z executable.")
    return parser.parse_args()


def extract_files_from_msi_main(
        msi_filepath: str = None,
        main_out_directory: str = None,
        sevenz_path: str = None
):
    """
    Extracts files from the MSI file using the MSI database.
    What can be extracted:
    - MSI file Table contents
    - MSI file Binary files
    - MSI file Icon files
    - MSI file ISSETUPFILES
    - MSI file Registry changes
    - MSI file CAB files
    - Application Installation files.
        These are extracted from the CAB files and renamed to their real names from the DB.
    - MSI file OLE metadata

    Usage:
        # You can create a python file with the following content and run it:
        from atomicshop.wrappers.ctyping.msi_windows_installer import extract_msi_main


        if __name__ == "__main__":
            extract_msi_main.extract_files_from_msi_main()

    Or you can just use the function with the appropriate parameters directly:
        extract_msi_main.extract_files_from_msi_main(
            msi_filepath=r"C:\\Setup.msi",
            main_out_directory=r"c:\\unpacked_msi",
            sevenz_path=r"C:\\7z.exe")

    :param msi_filepath: string, The path to the MSI file.
    :param main_out_directory: string, The main output directory.
    :param sevenz_path: string, The path to the 7z executable. If None, the default path is used, which assumes that 7z
        is in the PATH environment variable.
    :return:
    """

    args = parse_args()

    # If arguments to the function were not provided, use the arguments from the command line.
    if not msi_filepath:
        msi_filepath = args.msi_filepath
    if not main_out_directory:
        main_out_directory = args.output_directory
    if not sevenz_path:
        sevenz_path = args.sevenz_path

    # If not provided, raise an error.
    if not msi_filepath:
        print_api("The path to the MSI file is not provided with [-m].", color="red")
        return 1
    if not main_out_directory:
        print_api("The main output directory is not provided with [-o].", color="red")
        return 1
    if not sevenz_path:
        print_api(
            "The path to the 7z executable is not provided. Assuming 7z is in the PATH environment variable.",
            color="yellow")
        sevenz_path = "7z"

    if not sevenz_app_w.is_path_contains_7z_executable(sevenz_path):
        print_api("The path to 7z does not contain 7z executable", color="red")
        return 1

    if sevenz_path != "7z" and not os.path.isfile(sevenz_path):
        print_api("The path to 7z executable doesn't exist.", color="red")
        return 1

    if not sevenz_app_w.is_executable_a_7z(sevenz_path):
        print_api("Provided 7z executable is not 7z.", color="red")
        return 1

    # Create the main output directory.
    os.makedirs(main_out_directory, exist_ok=True)

    # Open the MSI database file.
    db_handle = base.create_open_db_handle(msi_filepath)

    embedded_files_directory = os.path.join(main_out_directory, EMBEDDED_FILES)

    # Extract files using the MSI database handle.
    tables.extract_table_contents_to_csv(db_handle, os.path.join(embedded_files_directory, TABLE_CONTENTS))
    tables.extract_binary_table_entries(db_handle, os.path.join(embedded_files_directory, BINARY_FILES))
    tables.extract_icon_table_entries(db_handle, os.path.join(embedded_files_directory, ICON_FILES))
    tables.extract_issetupfiles_table_entries(db_handle, os.path.join(embedded_files_directory, ISSETUPFILES))
    tables.extract_registry_changes(db_handle, os.path.join(embedded_files_directory, REGISTRY_CHANGES))

    # Extract CAB files from the MSI file.
    cab_files = tables.list_media_table_entries(db_handle)
    print(f"CAB files found: {cab_files}")
    extracted_cab_file_paths: list = tables.extract_cab_files_from_media(
        db_handle, os.path.join(embedded_files_directory, CAB_FILES))

    # Extract installation files from CAB files and rename them to their real names from DB.
    cabs.extract_files_from_cab(
        db_handle,
        extracted_cab_file_paths[0],
        os.path.join(main_out_directory, EXTRACTED_FILES),
        sevenz_path=sevenz_path)

    # Close the MSI database handle.
    msi.MsiCloseHandle(db_handle)

    # Extract OLE metadata from the MSI file.
    olefilew.extract_ole_metadata(msi_filepath, os.path.join(embedded_files_directory, OLE_METADATA))

    return 0

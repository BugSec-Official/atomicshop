import os
from pathlib import Path

from . import tables
from ....archiver import sevenz_app_w


def resolve_directory_path(directory_info, directory_key):
    parts = []
    current_key = directory_key
    while current_key:
        entry = directory_info.get(current_key)
        if entry:
            parts.append(entry['default_dir'])
            current_key = entry['parent']
        else:
            break
    if not parts:
        return ""
    return str(os.path.join(*reversed(parts)))


def rename_extracted_files_by_file_table_info(
        extracted_files_dir, file_table_info, component_table_info, directory_table_info):

    for file_key, info in file_table_info.items():
        component = info['component']
        directory_key = component_table_info[component]['directory']
        resolved_directory_path: str = resolve_directory_path(directory_table_info, directory_key)

        # Divide the path into parts and remove the first part if it is a 'SourceDir' and the last part if it is a dot.
        resolved_directory_parts = Path(resolved_directory_path).parts
        if resolved_directory_parts[-1] == '.':
            resolved_directory_parts = resolved_directory_parts[:-1]
        if resolved_directory_parts[0] == 'SourceDir':
            resolved_directory_parts = resolved_directory_parts[1:]
        resolved_directory_path = str(os.path.join(*resolved_directory_parts))

        extracted_path = os.path.join(extracted_files_dir, file_key)
        if os.path.exists(extracted_path):
            new_file_name = f"{info['file_name']}"
            new_file_path = os.path.join(extracted_files_dir, resolved_directory_path, new_file_name)
            os.makedirs(os.path.dirname(new_file_path), exist_ok=True)
            os.rename(extracted_path, new_file_path)
            print(f"Renamed: [{file_key}] to [{new_file_name}]")
        else:
            print(f"File not found: [{file_key}] in {extracted_path}")


def extract_files_from_cab(db_handle, main_cab_path: str, output_directory: str, sevenz_path: str = None):
    """
    Extracts the files from the CAB file using 7z executable and the MSI database handle to get the real file
    names and paths.
    :param db_handle: Database handle to the MSI database.
    :param main_cab_path: string, The path to the main CAB file.
    :param output_directory: string, The directory to extract the files to.
    :param sevenz_path: string, Full path to the 7z executable.
    :return:
    """

    # Get all the tables entries from the MSI database to correlate them while building the file paths and renaming.
    file_table_info = tables.get_file_table_info(db_handle)
    component_table_info = tables.get_component_table_info(db_handle)
    directory_table_info = tables.get_directory_table_info(db_handle)

    # Extract the contents of the CAB file (if there are several CAB files, they will be extracted as well).
    sevenz_app_w.extract_file(
        file_path=main_cab_path,
        extract_to=output_directory,
        sevenz_path=sevenz_path,
        force_overwrite=True
    )

    rename_extracted_files_by_file_table_info(
        output_directory, file_table_info, component_table_info, directory_table_info)

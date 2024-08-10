import os
import csv
import ctypes
from ctypes import wintypes

from . import base
from .base import msi


def get_column_names(db_handle, table_name):
    """Fetch column names for a specific table."""
    column_names = []
    query = f"SELECT `Name` FROM `_Columns` WHERE `Table`='{table_name}' ORDER BY `Number`"
    view_handle = base.create_open_execute_view_handle(db_handle, query)

    while True:
        record_handle = base.create_fetch_record_from_view_handle(view_handle)
        if not record_handle:
            break

        column_name = base.get_table_field_data_from_record(record_handle, field_index=1, data_type='stringw')
        if column_name:
            column_names.append(column_name)

    msi.MsiCloseHandle(record_handle)
    msi.MsiCloseHandle(view_handle)
    return column_names


def list_all_table_names(db_handle) -> list:
    """List all tables in the MSI database."""
    query = "SELECT `Name` FROM `_Tables`"
    view_handle = base.create_open_execute_view_handle(db_handle, query)

    tables: list = []
    while True:
        record_handle = base.create_fetch_record_from_view_handle(view_handle)

        # If record handle is empty then there is nothing more in the buffer, and we can stop the loop.
        if not record_handle:
            break

        tables.append(base.get_table_field_data_from_record(record_handle, field_index=1, data_type='stringw'))

    msi.MsiCloseHandle(record_handle)
    msi.MsiViewClose(view_handle)

    return tables


def get_table_contents(db_handle, table_name):
    """Fetch all contents of a specific table using ctypes."""
    view_handle = base.create_open_execute_view_handle(db_handle, f"SELECT * FROM `{table_name}`")
    contents = []

    # Fetch column names
    column_names = get_column_names(db_handle, table_name)
    contents.append(column_names)

    while True:
        record_handle = base.create_fetch_record_from_view_handle(view_handle)
        if not record_handle:
            break

        row = []
        field_count = msi.MsiRecordGetFieldCount(record_handle)

        for i in range(1, field_count + 1):
            # Try to fetch as a string
            buf_size = wintypes.DWORD(1024)
            buf = ctypes.create_unicode_buffer(buf_size.value)
            result = msi.MsiRecordGetStringW(record_handle, i, buf, ctypes.byref(buf_size))

            if result == 0:
                row.append(buf.value)
            elif result == 234:  # ERROR_MORE_DATA
                # Increase buffer size and try again
                buf_size = wintypes.DWORD(buf_size.value + 1)
                buf = ctypes.create_unicode_buffer(buf_size.value)
                result = msi.MsiRecordGetStringW(record_handle, i, buf, ctypes.byref(buf_size))
                if result == 0:
                    row.append(buf.value)
                else:
                    row.append(None)
            else:
                # Try to fetch as an integer
                int_value = ctypes.c_int()
                result = msi.MsiRecordGetInteger(record_handle, i, ctypes.byref(int_value))
                if result == 0:
                    row.append(int_value.value)
                else:
                    # Try to fetch as a stream
                    stream_size = wintypes.DWORD()
                    result = msi.MsiRecordReadStream(record_handle, i, None, ctypes.byref(stream_size))
                    if result == 0:
                        stream_data = ctypes.create_string_buffer(stream_size.value)
                        msi.MsiRecordReadStream(record_handle, i, stream_data, ctypes.byref(stream_size))
                        row.append(stream_data.raw)
                    else:
                        row.append(None)

        contents.append(row)
        msi.MsiCloseHandle(record_handle)

    msi.MsiCloseHandle(view_handle)
    return contents


def extract_table_contents_to_csv(db_handle, output_directory):
    """Extracts all table contents to separate CSV files."""

    os.makedirs(output_directory, exist_ok=True)

    # Get all the table names.
    table_names: list = list_all_table_names(db_handle)
    # Get all the table contents by fetching each table.
    table_contents = {table: get_table_contents(db_handle, table) for table in table_names}
    print(f"Tables and their contents have been fetched.")

    # Save each table to a separate CSV file
    for table, contents in table_contents.items():
        csv_file_path = os.path.join(output_directory, f"{table}.csv")
        with open(csv_file_path, "w", newline='') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerows(contents)
        print(f"Table {table} contents saved to {csv_file_path}")

    print("All table contents saved to separate CSV files in the 'tables' directory.")


def extract_binary_table_entries(db_handle, output_directory: str):
    os.makedirs(output_directory, exist_ok=True)

    # Create and execute a view to query the Binary table
    query = "SELECT Name, Data FROM Binary"
    view_handle = base.create_open_execute_view_handle(db_handle, query)

    while True:
        # Fetch a record from the view
        record_handle = base.create_fetch_record_from_view_handle(view_handle)
        if not record_handle:
            break

        # Get the binary name
        name = base.get_table_field_data_from_record(record_handle, field_index=1, data_type='stringw')

        # Get the size of the binary data
        data_size = msi.MsiRecordDataSize(record_handle, 2)
        if data_size == 0:
            continue

        # Read the binary data
        binary_data = base.get_table_field_data_from_record(
            record_handle, field_index=2, data_type='stream', buffer_size=data_size)

        # Save the binary data to a file
        output_filepath = os.path.join(output_directory, name)
        print(f"Extracting binary file [{name}] to {output_filepath}")
        with open(output_filepath, 'wb') as f:
            f.write(binary_data)

    msi.MsiCloseHandle(record_handle)
    msi.MsiCloseHandle(view_handle)


def extract_icon_table_entries(db_handle, output_directory: str):
    """Extracts icons from the Icon table in the specified MSI file."""
    os.makedirs(output_directory, exist_ok=True)

    query = "SELECT Name, Data FROM Icon"
    view_handle = base.create_open_execute_view_handle(db_handle, query)

    while True:
        # Fetch a record from the view
        record_handle = base.create_fetch_record_from_view_handle(view_handle)
        if not record_handle:
            break

        # Read the Name (field 1) and Data (field 2) from the record
        icon_filename = base.get_table_field_data_from_record(record_handle, 1, 'stringw')
        icon_data = base.get_table_field_data_from_record(record_handle, 2, 'stream')

        # Define the output file path
        output_file_path = os.path.join(output_directory, f"{icon_filename}")

        # Write the icon data to a file
        with open(output_file_path, 'wb') as icon_file:
            icon_file.write(icon_data)

        print(f"Extracted icon: {output_file_path}")

    # Close handles.
    msi.MsiCloseHandle(record_handle)
    msi.MsiCloseHandle(view_handle)


def extract_issetupfiles_table_entries(db_handle, output_directory: str):
    """Extracts icons from the Icon table in the specified MSI file."""
    os.makedirs(output_directory, exist_ok=True)

    query = "SELECT FileName, Stream FROM ISSetupFile"
    view_handle = base.create_open_execute_view_handle(db_handle, query)

    while True:
        # Fetch a record from the view
        record_handle = base.create_fetch_record_from_view_handle(view_handle)
        if not record_handle:
            break

        # Read the Name (field 1) and Data (field 2) from the record
        file_name = base.get_table_field_data_from_record(record_handle, 1, 'stringw')
        file_data = base.get_table_field_data_from_record(record_handle, 2, 'stream')

        # Define the output file path
        output_file_path = os.path.join(output_directory, f"{file_name}")

        # Write the icon data to a file
        with open(output_file_path, 'wb') as icon_file:
            icon_file.write(file_data)

        print(f"Extracted IsSetupFile: {output_file_path}")

    # Close handles.
    msi.MsiCloseHandle(record_handle)
    msi.MsiCloseHandle(view_handle)


def extract_registry_changes(db_handle, output_directory: str):
    """Extracts registry changes from the MSI file and writes them to a .reg file."""

    os.makedirs(output_directory, exist_ok=True)
    registry_file_path: str = os.path.join(output_directory, "registry_changes.reg")

    # Create and execute a view for the Registry table
    query = "SELECT `Root`, `Key`, `Name`, `Value` FROM `Registry`"
    view_handle = base.create_open_execute_view_handle(db_handle, query)

    with open(registry_file_path, 'w') as reg_file:
        # Write the .reg file header
        reg_file.write("Windows Registry Editor Version 5.00\n\n")

        while True:
            # Fetch a record from the view
            record_handle = base.create_fetch_record_from_view_handle(view_handle)
            if not record_handle:
                break

            # Read the Root (field 1), Key (field 2), Name (field 3), and Value (field 4) from the record
            root = int(base.get_table_field_data_from_record(record_handle, 1, 'stringw'))
            key = base.get_table_field_data_from_record(record_handle, 2, 'stringw')
            name = base.get_table_field_data_from_record(record_handle, 3, 'stringw')
            value = base.get_table_field_data_from_record(record_handle, 4, 'stringw')

            # Determine the root key name
            root_key = {
                0: "HKEY_CLASSES_ROOT",
                1: "HKEY_CURRENT_USER",
                2: "HKEY_LOCAL_MACHINE",
                3: "HKEY_USERS"
            }.get(root, "UNKNOWN_ROOT")

            # Format the registry entry
            if name:
                reg_entry = f'[{root_key}\\{key}]\n"{name}"="{value}"\n\n'
            else:
                reg_entry = f'[{root_key}\\{key}]\n@="{value}"\n\n'

            # Write the registry entry to the .reg file
            reg_file.write(reg_entry)

    msi.MsiCloseHandle(record_handle)
    msi.MsiCloseHandle(view_handle)


def list_media_table_entries(db_handle):
    """List all CAB files from the Media table."""
    query = "SELECT `Cabinet` FROM `Media`"
    media_view = base.create_open_execute_view_handle(db_handle, query)

    cab_files = []
    while True:
        record_handle = base.create_fetch_record_from_view_handle(media_view)
        if not record_handle:
            break

        # The CAB file names are prefixed with #
        cab_name = base.get_table_field_data_from_record(record_handle, field_index=1, data_type='stringw')
        cab_files.append(cab_name.strip("#"))

    msi.MsiCloseHandle(record_handle)
    msi.MsiCloseHandle(media_view)
    return cab_files


def extract_cab_files_from_media(db_handle, output_directory: str):
    """Extract all CAB files from the list."""
    os.makedirs(output_directory, exist_ok=True)

    query = "SELECT `Cabinet` FROM `Media` WHERE `Cabinet` IS NOT NULL"
    # Query to fetch CAB files from the Media table
    view_handle = base.create_open_execute_view_handle(db_handle, query)

    cabinet_name_list: list = []
    while True:
        record_handle = base.create_fetch_record_from_view_handle(view_handle)
        if not record_handle:
            break

        cabinet_name = base.get_table_field_data_from_record(record_handle, field_index=1, data_type='stringw')
        cabinet_name_list.append(cabinet_name)
    msi.MsiCloseHandle(record_handle)
    msi.MsiCloseHandle(view_handle)

    cab_file_paths: list = []
    for cabinet_name in cabinet_name_list:
        if cabinet_name.startswith("#"):
            cabinet_name = cabinet_name[1:]  # Remove the leading #

            cab_file_path = os.path.join(output_directory, cabinet_name)
            with open(cab_file_path, 'wb') as f:
                # Read the binary stream from the MSI package
                stream_query = f"SELECT `Data` FROM `_Streams` WHERE `Name`='{cabinet_name}'"
                stream_view = base.create_open_execute_view_handle(db_handle, stream_query)

                while True:
                    stream_record = base.create_fetch_record_from_view_handle(stream_view)
                    if not stream_record:
                        break

                    data = base.get_table_field_data_from_record(stream_record, field_index=1, data_type='stream')

                f.write(data)

                msi.MsiCloseHandle(stream_record)
                msi.MsiViewClose(stream_view)
                msi.MsiCloseHandle(stream_view)

            print(f"Extracted: {cabinet_name}")
            cab_file_paths.append(cab_file_path)

    print(f"CAB files extraction completed. Files are saved to {output_directory}")
    return cab_file_paths


def get_file_table_info(db_handle):
    query = "SELECT `File`, `FileName`, `Component_` FROM `File`"
    view_handle = base.create_open_execute_view_handle(db_handle, query)

    file_info = {}

    # Fetch the records
    while True:
        record_handle = base.create_fetch_record_from_view_handle(view_handle)
        if not record_handle:
            break

        file_key = base.get_table_field_data_from_record(record_handle, field_index=1, data_type='stringw')
        # Handle cases with multiple file names
        file_name = base.get_table_field_data_from_record(record_handle, field_index=2, data_type='stringw')
        file_name = file_name.split('|')[-1]
        component = base.get_table_field_data_from_record(record_handle, field_index=3, data_type='stringw')

        file_info[file_key] = {'file_name': file_name, 'component': component}

    msi.MsiCloseHandle(record_handle)
    msi.MsiCloseHandle(view_handle)

    return file_info


def get_component_table_info(db_handle):
    component_info = {}

    query = "SELECT `Component`, `Directory_` FROM `Component`"
    view_handle = base.create_open_execute_view_handle(db_handle, query)

    # Fetch the records
    while True:
        record_handle = base.create_fetch_record_from_view_handle(view_handle)
        if not record_handle:
            break

        component_key = base.get_table_field_data_from_record(record_handle, field_index=1, data_type='stringw')
        directory = base.get_table_field_data_from_record(record_handle, field_index=2, data_type='stringw')

        component_info[component_key] = {'directory': directory}

    msi.MsiCloseHandle(record_handle)
    msi.MsiCloseHandle(view_handle)

    return component_info


def get_directory_table_info(db_handle):
    directory_info = {}

    # Open a view to the Directory table
    query = "SELECT `Directory`, `Directory_Parent`, `DefaultDir` FROM `Directory`"
    view_handle = base.create_open_execute_view_handle(db_handle, query)

    # Fetch the records
    while True:
        record_handle = base.create_fetch_record_from_view_handle(view_handle)
        if not record_handle:
            break

        directory_key = base.get_table_field_data_from_record(record_handle, field_index=1, data_type='stringw')
        parent_key = base.get_table_field_data_from_record(record_handle, field_index=2, data_type='stringw')

        # Handle cases with multiple directory names with '|' character.
        default_dir_buffer = base.get_table_field_data_from_record(record_handle, field_index=3, data_type='stringw')
        default_dir = default_dir_buffer.split('|')[-1]

        directory_info[directory_key] = {'parent': parent_key, 'default_dir': default_dir}

    msi.MsiCloseHandle(record_handle)
    msi.MsiCloseHandle(view_handle)

    return directory_info


def _get_stream_table_info(db_handle):
    """
    Get stream table info.
    Basically this function gets all the file names and their binaries from the _Streams table.
    All the above functions already do this in a more structured way.
    There is nothing more in this function that you will find, unless there is a file that will not be in other tables,
    which is very unlikely.

    The only thing that may be of interest is the '\x05SummaryInformation' stream, which is a special stream that
    contains information about the MSI package. But we already use the 'wrappers.olefilew.extract_ole_metadata'
    function to get this information in the parsed way.
    :param db_handle:
    :return:
    """
    query = "SELECT `Name`, `Data` FROM `_Streams`"
    view_handle = base.create_open_execute_view_handle(db_handle, query)

    stream_info = {}

    while True:
        record_handle = base.create_fetch_record_from_view_handle(view_handle)
        if not record_handle:
            break

        stream_name = base.get_table_field_data_from_record(record_handle, field_index=1, data_type='stringw')
        stream_data = base.get_table_field_data_from_record(record_handle, field_index=2, data_type='stream')

        stream_info[stream_name] = stream_data

    msi.MsiCloseHandle(record_handle)
    msi.MsiCloseHandle(view_handle)

    return stream_info

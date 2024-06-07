from typing import Literal
import ctypes
from ctypes import wintypes


# Load Windows Installer functions
msi = ctypes.windll.msi


# Constants
MSIDBOPEN_READONLY = 0
ERROR_NO_MORE_ITEMS = 259


def create_open_db_handle(msi_filepath):
    """Create a database handle for the specified MSI file."""
    db_handle = ctypes.c_void_p()

    result = msi.MsiOpenDatabaseW(msi_filepath, MSIDBOPEN_READONLY, ctypes.byref(db_handle))
    if result != 0:
        print(f"Failed to open MSI database. Error code: {result}")
        raise ctypes.WinError(result)
    return db_handle


def create_open_execute_view_handle(db_handle, query):
    """Create a view handle for the specified query."""
    # Create view handle.
    view_handle = ctypes.c_void_p()

    # Open the view.
    result = msi.MsiDatabaseOpenViewW(db_handle, query, ctypes.byref(view_handle))
    if result != 0:
        print(f"Failed to open view. Error code: {result}")
        msi.MsiCloseHandle(db_handle)
        raise ctypes.WinError(result)

    # Execute the view.
    result = msi.MsiViewExecute(view_handle, None)
    if result != 0:
        print(f"Failed to execute view. Error code: {result}")
        msi.MsiCloseHandle(view_handle)
        msi.MsiCloseHandle(db_handle)
        raise ctypes.WinError(result)

    return view_handle


def create_fetch_record_from_view_handle(view_handle):
    """Fetch a record from the specified view handle."""
    # Fetch the record handle.
    record_handle = ctypes.c_void_p()

    # Fetch the record.
    fetch_record_result = msi.MsiViewFetch(view_handle, ctypes.byref(record_handle))
    if fetch_record_result == ERROR_NO_MORE_ITEMS:
        msi.MsiCloseHandle(view_handle)
        return record_handle
    elif fetch_record_result != 0:
        print(f"Failed to fetch record. Error code: {fetch_record_result}")
        msi.MsiCloseHandle(view_handle)
        raise ctypes.WinError(fetch_record_result)

    return record_handle


def get_table_field_data_from_record(
        record_handle,
        field_index,
        data_type: Literal['stringw', 'integer', 'stream'],
        buffer_size: int = 2048
):
    """
    Read data from a specific field in a record.
    :param record_handle: Record handle.
    :param field_index: The field index. Example: 2 for the second field.
        Name,Data
        field_index = 1 for Name
        field_index = 2 for Data
    :param data_type: The type of data to read.
        stringw: Read the data as a wide string.
        integer: Read the data as an integer.
        stream: Read the data as a binary stream (bytes).
    :param buffer_size: The size of the buffer to use when reading the data.
    :return:
    """

    if data_type == 'stringw':
        buf_size = wintypes.DWORD(buffer_size)
        buf = ctypes.create_unicode_buffer(buf_size.value)
        result = msi.MsiRecordGetStringW(record_handle, field_index, buf, ctypes.byref(buf_size))
        if result != 0:
            if result == 234:
                print("Buffer size too small. Try again with a larger buffer.")
            print(f"Failed to get string from record. Error code: {result}")
            msi.MsiCloseHandle(record_handle)
            raise ctypes.WinError(result)
        return str(buf.value)

    elif data_type == 'integer':
        int_value = ctypes.c_int()
        result = msi.MsiRecordGetInteger(record_handle, field_index, ctypes.byref(int_value))
        if result != 0:
            print(f"Failed to get integer from record. Error code: {result}")
            msi.MsiCloseHandle(record_handle)
            raise ctypes.WinError(result)
        return int_value.value

    elif data_type == 'stream':
        # stream_size = wintypes.DWORD()
        # result = msi.MsiRecordReadStream(record_handle, field_index, None, ctypes.byref(stream_size))
        # if result != 0:
        #     print(f"Failed to read stream data. Error code: {result}")
        #     msi.MsiCloseHandle(record_handle)
        #     raise ctypes.WinError(result)
        #
        # stream_data = ctypes.create_string_buffer(stream_size.value)
        # msi.MsiRecordReadStream(record_handle, field_index, stream_data, ctypes.byref(stream_size))
        # return stream_data.raw

        buffer = ctypes.create_string_buffer(buffer_size)
        read_size = wintypes.DWORD(buffer_size)
        data = bytearray()

        while True:
            result = msi.MsiRecordReadStream(record_handle, field_index, buffer, ctypes.byref(read_size))
            if result != 0 or read_size.value == 0:
                break
            data.extend(buffer.raw[:read_size.value])

        return data

    else:
        raise ValueError(f"Invalid data type: {data_type}. Valid options are 'stringw', 'integer', 'stream'.")

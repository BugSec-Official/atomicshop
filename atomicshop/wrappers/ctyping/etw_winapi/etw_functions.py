import ctypes
from ctypes.wintypes import ULONG
import uuid

from . import const


# Function to stop and delete ETW session
def stop_and_delete_etw_session(session_name) -> tuple[bool, int]:
    """
    Stop and delete ETW session.

    :param session_name: The name of the session to stop and delete.
    :return: A tuple containing a boolean indicating success and an integer status code.
        True, 0: If the session was stopped and deleted successfully.
        False, <status>: If the session could not be stopped and deleted and the status code, why it failed.
    """

    session_name_unicode = ctypes.create_unicode_buffer(session_name)
    properties_size = ctypes.sizeof(const.EVENT_TRACE_PROPERTIES) + 1024  # Adjust buffer size if needed
    properties = ctypes.create_string_buffer(properties_size)

    trace_properties = ctypes.cast(properties, ctypes.POINTER(const.EVENT_TRACE_PROPERTIES)).contents
    trace_properties.Wnode.BufferSize = properties_size
    trace_properties.Wnode.Flags = const.WNODE_FLAG_TRACED_GUID
    trace_properties.Wnode.Guid = const.GUID()  # Ensure a GUID is provided if necessary
    trace_properties.LoggerNameOffset = ctypes.sizeof(const.EVENT_TRACE_PROPERTIES)

    ctypes.memmove(ctypes.addressof(properties) + trace_properties.LoggerNameOffset,
                   session_name_unicode, ctypes.sizeof(session_name_unicode))

    status = const.advapi32.ControlTraceW(
        None, session_name_unicode, ctypes.byref(trace_properties), const.EVENT_TRACE_CONTROL_STOP)

    if status != 0:
        # print(f"Failed to stop and delete ETW session: {status}")
        return False, status
    else:
        # print("ETW session stopped and deleted successfully.")
        return True, status


def get_all_providers() -> list[tuple[any, uuid.UUID]]:
    """
    Get all ETW providers available on the system.

    :return: A list of tuples containing the provider name and GUID.
    """

    providers_info_size = ULONG(0)
    status = const.tdh.TdhEnumerateProviders(None, ctypes.byref(providers_info_size))

    # Initial allocation
    buffer = (ctypes.c_byte * providers_info_size.value)()
    providers_info = ctypes.cast(buffer, ctypes.POINTER(const.PROVIDER_ENUMERATION_INFO))

    # Loop to handle resizing
    while True:
        status = const.tdh.TdhEnumerateProviders(providers_info, ctypes.byref(providers_info_size))

        if status == 0:
            break
        elif status == 0x8007007A:  # ERROR_INSUFFICIENT_BUFFER
            buffer = (ctypes.c_byte * providers_info_size.value)()
            providers_info = ctypes.cast(buffer, ctypes.POINTER(const.PROVIDER_ENUMERATION_INFO))
        else:
            raise ctypes.WinError(status)

    provider_count = providers_info.contents.NumberOfProviders
    provider_array = ctypes.cast(
        ctypes.addressof(providers_info.contents) + ctypes.sizeof(const.PROVIDER_ENUMERATION_INFO),
        ctypes.POINTER(const.PROVIDER_INFORMATION * provider_count))

    providers = []
    for i in range(provider_count):
        provider = provider_array.contents[i]
        provider_name_offset = provider.ProviderNameOffset
        provider_name_ptr = ctypes.cast(
            ctypes.addressof(providers_info.contents) + provider_name_offset, ctypes.c_wchar_p)
        provider_name = provider_name_ptr.value
        provider_guid = uuid.UUID(bytes_le=bytes(provider.ProviderId))
        providers.append((provider_name, provider_guid))

    return providers


def list_etw_sessions() -> list[dict]:
    """
    List all running ETW sessions.

    :return: A list of dictionaries containing the names of all running ETW sessions and their log files.
    """
    # Create an array of EVENT_TRACE_PROPERTIES pointers
    PropertiesArrayType = ctypes.POINTER(const.EVENT_TRACE_PROPERTIES) * const.MAXIMUM_LOGGERS
    properties_array = PropertiesArrayType()
    for i in range(const.MAXIMUM_LOGGERS):
        properties = const.EVENT_TRACE_PROPERTIES()
        properties.Wnode.BufferSize = ctypes.sizeof(const.EVENT_TRACE_PROPERTIES)
        properties_array[i] = ctypes.pointer(properties)

    # Define the number of loggers variable
    logger_count = ULONG(const.MAXIMUM_LOGGERS)

    # Call QueryAllTraces
    status = const.QueryAllTraces(properties_array, const.MAXIMUM_LOGGERS, ctypes.byref(logger_count))
    if status != 0:
        raise Exception(f"QueryAllTraces failed, error code: {status}")

    # Extract session names
    session_list: list = []
    for i in range(logger_count.value):
        logger_name = None
        logfile_path = None

        properties = properties_array[i].contents
        if properties.LoggerNameOffset != 0:
            logger_name_address = ctypes.addressof(properties) + properties.LoggerNameOffset
            logger_name = ctypes.wstring_at(logger_name_address)
        if properties.LogFileNameOffset != 0:
            logfile_name_address = ctypes.addressof(properties) + properties.LogFileNameOffset
            logfile_path = ctypes.wstring_at(logfile_name_address)

        session_list.append({
            'session_name': logger_name,
            'log_file': logfile_path
        })

    return session_list

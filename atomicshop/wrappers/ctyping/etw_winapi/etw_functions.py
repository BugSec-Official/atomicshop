import ctypes
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

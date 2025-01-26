import ctypes
import queue
from ctypes.wintypes import ULONG
import uuid
from typing import Literal

from . import const
from ....etws import providers

class ETWSessionExists(Exception):
    pass


# Convert the GUID string to a GUID structure
def _string_to_guid(guid_string):
    guid_string = guid_string.strip('{}')  # Remove curly braces
    parts = guid_string.split('-')
    return const.GUID(
        Data1=int(parts[0], 16),
        Data2=int(parts[1], 16),
        Data3=int(parts[2], 16),
        Data4=(ctypes.c_ubyte * 8)(*[
            int(parts[3][i:i+2], 16) for i in range(0, 4, 2)
        ] + [
            int(parts[4][i:i+2], 16) for i in range(0, 12, 2)
        ])
    )


# Set up the ETW session
def start_etw_session(
        session_name: str,
        provider_guid_list: list = None,
        provider_name_list: list = None,
        verbosity_mode: int = 4,
        maximum_buffers: int = 38
) -> const.TRACEHANDLE:
    """
    Start an ETW session and enable the specified provider.

    :param session_name: The name of the session to start.
    :param provider_guid_list: The GUID list of the providers to enable.
    :param provider_name_list: The name list of the providers to enable.
    :param verbosity_mode: The verbosity level of the events to capture.
        0 - Always: Capture all events. This is typically used for critical events that should always be logged.
        1 - Critical: Capture critical events that indicate a severe problem.
        2 - Error: Capture error events that indicate a problem but are not critical.
        3 - Warning: Capture warning events that indicate a potential problem.
        4 - Information: Capture informational events that are not indicative of problems.
        5 - Verbose: Capture detailed trace events for diagnostic purposes.
    :param maximum_buffers: The maximum number of buffers to use.
        0 or 16: The default value of ETW class. If you put 0, it will be converted to 16 by default by ETW itself.
        38: The maximum number of buffers that can be used.

        Event Handling Capacity:
            16 Buffers: With fewer buffers, the session can handle a smaller volume of events before needing to flush
            the buffers to the log file or before a real-time consumer needs to process them. If the buffers fill up
            quickly and cannot be processed in time, events might be lost.
            38 Buffers: With more buffers, the session can handle a higher volume of events. This reduces the
            likelihood of losing events in high-traffic scenarios because more events can be held in memory before
            they need to be processed or written to a log file.
        Performance Considerations:
            16 Buffers: Requires less memory, but may be prone to event loss under heavy load if the buffers fill up
            faster than they can be processed.
            38 Buffers: Requires more memory, but can improve reliability in capturing all events under heavy load by
            providing more buffer space. However, it can also increase the memory footprint of the application or
            system running the ETW session.
    """

    if not provider_guid_list and not provider_name_list:
        raise ValueError("Either 'provider_guid_list' or 'provider_name_list' must be provided")
    elif provider_guid_list and provider_name_list:
        raise ValueError("Only one of 'provider_guid_list' or 'provider_name_list' must be provided")

    if provider_name_list:
        provider_guid_list = []
        for provider_name in provider_name_list:
            provider_guid_list.append(providers.get_provider_guid_by_name(provider_name))

        # (1) Allocate a buffer large enough for EVENT_TRACE_PROPERTIES + space for 2 strings
        #     The typical approach is to allow enough space for:
        #       - The structure
        #       - The "LoggerName" string
        #       - The "LogFileName" string (even if we don't use it, we must leave offset space)
        #
        props_size = ctypes.sizeof(const.EVENT_TRACE_PROPERTIES)
        # Add space for 2 x 1024 wide-chars (one for LoggerName, one for LogFileName)
        # Each wide char = ctypes.sizeof(ctypes.c_wchar).
        props_size += (2 * 1024 * ctypes.sizeof(ctypes.c_wchar))  # for logger name
        props_size += (2 * 1024 * ctypes.sizeof(ctypes.c_wchar))  # for log file name

        properties_buffer = ctypes.create_string_buffer(props_size)
        properties_ptr = ctypes.cast(properties_buffer, ctypes.POINTER(const.EVENT_TRACE_PROPERTIES))
        props = properties_ptr.contents

        # (2) Fill in basic fields
        props.Wnode.BufferSize = props_size
        props.Wnode.Flags = const.WNODE_FLAG_TRACED_GUID  # 0x00020000
        props.Wnode.ClientContext = 1  # QPC clock
        props.BufferSize = 1024
        props.MinimumBuffers = 1
        props.MaximumBuffers = maximum_buffers
        props.MaximumFileSize = 0
        props.LogFileMode = const.EVENT_TRACE_REAL_TIME_MODE  # real-time
        props.FlushTimer = 1
        props.EnableFlags = 0

        # (3) Indicate where in this allocated buffer the strings should go
        struct_size = ctypes.sizeof(const.EVENT_TRACE_PROPERTIES)
        props.LoggerNameOffset = struct_size
        props.LogFileNameOffset = struct_size + (2 * 1024 * ctypes.sizeof(ctypes.c_wchar))

        # (4) Copy the session name into the LoggerName space
        logger_name_address = ctypes.addressof(properties_buffer) + props.LoggerNameOffset
        session_name_wchar = ctypes.create_unicode_buffer(session_name)
        ctypes.memmove(
            logger_name_address,
            session_name_wchar,
            len(session_name) * ctypes.sizeof(ctypes.c_wchar)
        )

        # (5) Start the session
        session_handle = const.TRACEHANDLE(0)
        status = const.StartTrace(
            ctypes.byref(session_handle),
            session_name,  # The session name as an LPCWSTR
            properties_ptr  # pointer to EVENT_TRACE_PROPERTIES
        )

        if status != 0:
            # 183 => ERROR_ALREADY_EXISTS
            if status == 183:
                raise ETWSessionExists(f"ETW session [{session_name}] already exists")
            else:
                raise Exception(f"StartTraceW failed with error code {status}")

        # (6) If we have providers to enable, enable each
        if provider_guid_list:
            for guid_str in provider_guid_list:
                guid_struct = _string_to_guid(guid_str)

                # Typically you'd do something like:
                #   advapi32.EnableTraceEx2(TRACEHANDLE, PGUID, CONTROL_CODE, LEVEL, KW, KW, TIMEOUT, FILTER)

                enable_status = const.EnableTraceEx2(
                    session_handle,  # The session handle
                    ctypes.byref(guid_struct),  # The provider GUID
                    const.EVENT_CONTROL_CODE_ENABLE_PROVIDER,  # 1 => enable
                    verbosity_mode,  # level
                    0xFFFFFFFFFFFFFFFF, # matchAnyKeyword
                    0,  # matchAllKeyword
                    0,  # timeout
                    None  # enableParameters (optional)
                )

                if enable_status != 0:
                    raise Exception(
                        f"EnableTraceEx2 failed for provider {guid_str} (error={enable_status})"
                    )

        print(f"ETW session '{session_name}' started successfully.")
        return session_handle


# Function to stop and delete ETW session
def stop_and_delete_etw_session(session_name: str) -> tuple[bool, int]:
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


@const.EVENT_CALLBACK_TYPE
def _default_callback(
        event_record_ptr
):
    """
    This function will be called by Windows for every incoming ETW event.
    'event_record_ptr' is a pointer to an EVENT_RECORD structure.
    """
    # Convert pointer to a Python EVENT_RECORD object
    event_record = event_record_ptr.contents

    # Do something with event_record (e.g., parse via TDH)
    print("Received an ETW event!", event_record.EventHeader.ProviderId)


def start_etw_consumer(
        session_name: str,
        record_queue: queue.Queue
):
    """
    Attach to an existing real-time ETW session by 'session_name'
    using the "new" EVENT_RECORD callback approach.
    This call blocks until the ETW session is stopped or an error occurs.
    """
    # 1) Create a closure callback that references the queue
    #    We define an inner function that sees 'record_queue' from outer scope.
    #    Then we wrap that in EVENT_CALLBACK_TYPE.
    if record_queue is not None:
        @const.EVENT_CALLBACK_TYPE
        def _queue_callback(event_record_ptr):
            event_record = event_record_ptr.contents
            # # Example: put a simple dict with the provider ID & possibly more info
            # record_queue.put({
            #     "provider_id": str(event_record.EventHeader.ProviderId),
            #     "process_id": event_record.EventHeader.ProcessId,
            #     "thread_id": event_record.EventHeader.ThreadId,
            #     # ... more fields or parse them with TdhGetEventInformation, etc.
            # })
            print("Received an ETW event!", event_record.EventHeader.ProviderId)
            record_queue.put(event_record)
    else:
        _queue_callback = _default_callback

    # Keep a reference to the callback so Python doesn't GC it.
    start_etw_consumer._callback_ref = _queue_callback

    # Prepare the EVENT_TRACE_LOGFILE structure
    logfile = const.EVENT_TRACE_LOGFILE()
    # You can also do: logfile.LoggerName = session_name
    # If you assign session_name (a Python str), ctypes automatically converts it to a temporary c_wchar_p under the hood.
    # logfile.LoggerName = ctypes.c_wchar_p(session_name)
    logfile.LoggerName = session_name
    logfile.LogFileName = None  # Real-time, not from a file
    logfile.ProcessTraceMode = (const.PROCESS_TRACE_MODE_REAL_TIME | const.PROCESS_TRACE_MODE_EVENT_RECORD)

    # Point to our Python callback
    logfile.EventRecordCallback = const.EVENT_RECORD_CALLBACK(_default_callback)

    # Open the trace
    trace_handle = const.OpenTrace(ctypes.byref(logfile))
    if trace_handle == const.INVALID_PROCESSTRACE_HANDLE:
        error_code = ctypes.get_last_error()
        raise OSError(f"OpenTrace failed with error code: {error_code}")

    # trace_handle is actually an unsigned long, but in 64-bit it's a 64-bit handle.
    # We'll create an array of one handle for ProcessTrace:
    trace_handle_array = (ctypes.c_uint64 * 1)(trace_handle)

    # Blocking call - will not return until the session is stopped (or error).
    status = const.ProcessTrace(
        trace_handle_array,
        1,  # HandleCount = 1
        None,  # StartTime = None
        None  # EndTime = None
    )
    if status != 0:
        raise OSError(f"ProcessTrace failed with error code: {status}")

    print("ProcessTrace returned. ETW consumer finished.")


def start_etw_consumer_in_thread(
        session_name: str,
        record_queue: queue.Queue
):
    """
    Start an ETW consumer in a separate thread.
    """
    import threading

    def _start_etw_consumer():
        start_etw_consumer(session_name, record_queue)

    thread = threading.Thread(target=_start_etw_consumer)
    thread.start()


def get_all_providers(key_as: Literal['name', 'guid'] = 'name') -> dict:
    """
    Get all ETW providers available on the system.

    :param key_as: The key to use in the dictionary, either 'name' or 'guid'.
        'name': The provider name is used as the key, the guid as the value.
        'guid': The provider guid is used as the key, the name as the value.
    :return: dict containing the provider name and GUID.
    """

    if key_as not in ['name', 'guid']:
        raise ValueError("key_as must be either 'name' or 'guid'")

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

    providers: dict = {}
    for i in range(provider_count):
        provider = provider_array.contents[i]
        provider_name_offset = provider.ProviderNameOffset
        provider_name_ptr = ctypes.cast(
            ctypes.addressof(providers_info.contents) + provider_name_offset, ctypes.c_wchar_p)
        provider_name = provider_name_ptr.value
        provider_guid = uuid.UUID(bytes_le=bytes(provider.ProviderId))
        provider_guid_string = str(provider_guid)

        if key_as == 'name':
            providers[provider_name] = provider_guid_string
        elif key_as == 'guid':
            providers[provider_guid_string] = provider_name

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

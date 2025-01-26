import ctypes
from ctypes import wintypes
from ctypes.wintypes import ULONG


# Constants
EVENT_TRACE_CONTROL_STOP = 1
WNODE_FLAG_TRACED_GUID = 0x00020000
EVENT_TRACE_REAL_TIME_MODE = 0x00000100
EVENT_CONTROL_CODE_ENABLE_PROVIDER = 1

MAXIMUM_LOGGERS = 64
ULONG64 = ctypes.c_uint64
UCHAR = ctypes.c_ubyte

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
TRACEHANDLE = ULONG64

PROCESS_TRACE_MODE_EVENT_RECORD = 0x10000000     # new event-record callback
PROCESS_TRACE_MODE_REAL_TIME = 0x00000100
INVALID_PROCESSTRACE_HANDLE = 0xFFFFFFFFFFFFFFFF  # Often -1 in 64-bit


"""
wintypes.DWORD = wintypes.ULONG = ctypes.c_ulong: 32-bit unsigned integer
wintypes.WORD = wintypes.USHORT = ctypes.c_ushort: 16-bit unsigned integer
wintypes.BYTE = ctypes.c_ubyte: 8-bit unsigned integer
wintypes.LARGE_INTEGER is a structure (or union in C terms), can represent both signed and unsigned 
    64-bit values depending on context.
ctypes.c_ulonglong is a simple data type representing an unsigned 64-bit integer.
"""


# Define GUID structure
class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8)
    ]


# Define WNODE_HEADER
class WNODE_HEADER(ctypes.Structure):
    _fields_ = [
        ("BufferSize", wintypes.ULONG),
        ("ProviderId", wintypes.ULONG),
        ("HistoricalContext", wintypes.LARGE_INTEGER),
        ("TimeStamp", wintypes.LARGE_INTEGER),
        ("Guid", GUID),
        ("ClientContext", wintypes.ULONG),
        ("Flags", wintypes.ULONG)
    ]


class EVENT_TRACE_PROPERTIES(ctypes.Structure):
    _fields_ = [
        ("Wnode", WNODE_HEADER),
        ("BufferSize", wintypes.ULONG),
        ("MinimumBuffers", wintypes.ULONG),
        ("MaximumBuffers", wintypes.ULONG),
        ("MaximumFileSize", wintypes.ULONG),
        ("LogFileMode", wintypes.ULONG),
        ("FlushTimer", wintypes.ULONG),
        ("EnableFlags", wintypes.ULONG),
        ("AgeLimit", wintypes.LONG),
        ("NumberOfBuffers", wintypes.ULONG),
        ("FreeBuffers", wintypes.ULONG),
        ("EventsLost", wintypes.ULONG),
        ("BuffersWritten", wintypes.ULONG),
        ("LogBuffersLost", wintypes.ULONG),
        ("RealTimeBuffersLost", wintypes.ULONG),
        ("LoggerThreadId", wintypes.HANDLE),
        ("LogFileNameOffset", wintypes.ULONG),
        ("LoggerNameOffset", wintypes.ULONG)
    ]


class TRACE_LOGFILE_HEADER(ctypes.Structure):
    _fields_ = [
        ("BufferSize", wintypes.ULONG),
        ("Version", wintypes.ULONG),
        ("ProviderVersion", wintypes.ULONG),
        ("NumberOfProcessors", wintypes.ULONG),
        ("EndTime", wintypes.LARGE_INTEGER),
        ("TimerResolution", wintypes.ULONG),
        ("MaximumFileSize", wintypes.ULONG),
        ("LogFileMode", wintypes.ULONG),
        ("BuffersWritten", wintypes.ULONG),
        ("StartBuffers", wintypes.ULONG),
        ("PointerSize", wintypes.ULONG),
        ("EventsLost", wintypes.ULONG),
        ("CpuSpeedInMHz", wintypes.ULONG),
        ("LoggerName", wintypes.WCHAR * 256),
        ("LogFileName", wintypes.WCHAR * 256),
        ("TimeZone", wintypes.LPVOID),
        ("BootTime", wintypes.LARGE_INTEGER),
        ("PerfFreq", wintypes.LARGE_INTEGER),
        ("StartTime", wintypes.LARGE_INTEGER),
        ("ReservedFlags", wintypes.ULONG),
        ("BuffersLost", wintypes.ULONG)
    ]


class EVENT_TRACE_HEADER(ctypes.Structure):
    _fields_ = [
        ("Size", wintypes.USHORT),
        ("FieldTypeFlags", wintypes.USHORT),
        ("Version", wintypes.USHORT),
        ("Class", wintypes.USHORT),  # EVENT_TRACE_CLASS
        ("Type", ctypes.c_ubyte),
        ("Level", ctypes.c_ubyte),
        ("Channel", ctypes.c_ubyte),
        ("Flags", ctypes.c_ubyte),
        ("InstanceId", wintypes.USHORT),
        ("ParentInstanceId", wintypes.USHORT),
        ("ParentGuid", GUID),
        ("Timestamp", wintypes.LARGE_INTEGER),
        ("Guid", GUID),
        ("ProcessorTime", wintypes.ULONG),
        ("ThreadId", wintypes.ULONG),
        ("ProcessId", wintypes.ULONG),
        ("KernelTime", wintypes.ULONG),
        ("UserTime", wintypes.ULONG),
    ]


class EVENT_TRACE(ctypes.Structure):
    _fields_ = [
        ("Header", EVENT_TRACE_HEADER),
        ("InstanceId", wintypes.DWORD),
        ("ParentInstanceId", wintypes.DWORD),
        ("ParentGuid", GUID),
        ("MofData", ctypes.c_void_p),
        ("MofLength", wintypes.ULONG),
        ("ClientContext", wintypes.ULONG)
    ]


class EVENT_TRACE_LOGFILEW(ctypes.Structure):
    _fields_ = [
        ("LogFileName", ctypes.c_wchar_p),
        ("LoggerName", ctypes.c_wchar_p),
        ("CurrentTime", wintypes.LARGE_INTEGER),
        ("BuffersRead", wintypes.ULONG),
        ("ProcessTraceMode", wintypes.ULONG),
        ("CurrentEvent", EVENT_TRACE),
        ("LogfileHeader", TRACE_LOGFILE_HEADER),
        ("BufferCallback", ctypes.c_void_p),  # Placeholder for buffer callback
        ("BufferSize", wintypes.ULONG),
        ("Filled", wintypes.ULONG),
        ("EventsLost", wintypes.ULONG),
        ("EventCallback", ctypes.CFUNCTYPE(None, ctypes.POINTER(EVENT_TRACE))),
        ("Context", ULONG64)
    ]


class EVENT_DESCRIPTOR(ctypes.Structure):
    _fields_ = [
        ("Id", wintypes.USHORT),
        ("Version", wintypes.BYTE),
        ("Channel", wintypes.BYTE),
        ("Level", wintypes.BYTE),
        ("Opcode", wintypes.BYTE),
        ("Task", wintypes.USHORT),
        ("Keyword", ULONG64),
    ]


class EVENT_HEADER(ctypes.Structure):
    _fields_ = [
        ("Size", wintypes.USHORT),
        ("HeaderType", wintypes.USHORT),
        ("Flags", wintypes.USHORT),
        ("EventProperty", wintypes.USHORT),
        ("ThreadId", wintypes.ULONG),
        ("ProcessId", wintypes.ULONG),
        ("TimeStamp", wintypes.LARGE_INTEGER),
        ("ProviderId", GUID),
        ("EventDescriptor", EVENT_DESCRIPTOR),
        ("ProcessorTime", ULONG64),
        ("ActivityId", GUID),
        ("RelatedActivityId", GUID),
    ]


class ETW_BUFFER_CONTEXT(ctypes.Structure):
    _fields_ = [('ProcessorNumber', ctypes.c_ubyte),
                ('Alignment', ctypes.c_ubyte),
                ('LoggerId', ctypes.c_ushort)]


class EVENT_HEADER_EXTENDED_DATA_ITEM(ctypes.Structure):
    _fields_ = [
        ('Reserved1', ctypes.c_ushort),
        ('ExtType', ctypes.c_ushort),
        ('Linkage', ctypes.c_ushort),    # struct{USHORT :1, USHORT :15}
        ('DataSize', ctypes.c_ushort),
        ('DataPtr', ctypes.c_ulonglong)
    ]


class EVENT_RECORD(ctypes.Structure):
    _fields_ = [
        ('EventHeader', EVENT_HEADER),
        ('BufferContext', ETW_BUFFER_CONTEXT),
        ('ExtendedDataCount', ctypes.c_ushort),
        ('UserDataLength', ctypes.c_ushort),
        ('ExtendedData', ctypes.POINTER(EVENT_HEADER_EXTENDED_DATA_ITEM)),
        ('UserData', ctypes.c_void_p),
        ('UserContext', ctypes.c_void_p)
    ]


class EVENT_TRACE_LOGFILE(ctypes.Structure):
    pass


EVENT_RECORD_CALLBACK = ctypes.WINFUNCTYPE(None, ctypes.POINTER(EVENT_RECORD))
EVENT_TRACE_BUFFER_CALLBACK = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.POINTER(EVENT_TRACE_LOGFILE))


class EVENT_TRACE_LOGFILE(ctypes.Structure):
    _fields_ = [
        ('LogFileName', ctypes.c_wchar_p),
        ('LoggerName', ctypes.c_wchar_p),
        ('CurrentTime', ctypes.c_longlong),
        ('BuffersRead', ctypes.c_ulong),
        ('ProcessTraceMode', ctypes.c_ulong),
        ('CurrentEvent', EVENT_TRACE),
        ('LogfileHeader', TRACE_LOGFILE_HEADER),
        ('BufferCallback', EVENT_TRACE_BUFFER_CALLBACK),
        ('BufferSize', ctypes.c_ulong),
        ('Filled', ctypes.c_ulong),
        ('EventsLost', ctypes.c_ulong),
        ('EventRecordCallback', EVENT_RECORD_CALLBACK),
        ('IsKernelTrace', ctypes.c_ulong),
        ('Context', ctypes.c_void_p)
    ]


# Define the callback type for processing events
EVENT_CALLBACK_TYPE = ctypes.WINFUNCTYPE(None, ctypes.POINTER(EVENT_RECORD))


class PROVIDER_ENUMERATION_INFO(ctypes.Structure):
    _fields_ = [
        ("NumberOfProviders", ULONG),
        ("Reserved", ULONG),
    ]


class PROVIDER_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("ProviderId", ctypes.c_byte * 16),
        ("SchemaSource", ULONG),
        ("ProviderNameOffset", ULONG),
    ]


# Load the necessary library
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
tdh = ctypes.windll.tdh

# Define necessary TDH functions
tdh.TdhEnumerateProviders.argtypes = [ctypes.POINTER(PROVIDER_ENUMERATION_INFO), ctypes.POINTER(ULONG)]
tdh.TdhEnumerateProviders.restype = ULONG


# Make sure StartTraceW has proper argtypes (if not set in consts)
StartTrace = advapi32.StartTraceW
StartTrace.argtypes = [
    ctypes.POINTER(TRACEHANDLE),
    wintypes.LPCWSTR,
    ctypes.POINTER(EVENT_TRACE_PROPERTIES)
]
StartTrace.restype = wintypes.ULONG


class EVENT_FILTER_DESCRIPTOR(ctypes.Structure):
    _fields_ = [('Ptr', ctypes.c_ulonglong),
                ('Size', ctypes.c_ulong),
                ('Type', ctypes.c_ulong)]


class ENABLE_TRACE_PARAMETERS(ctypes.Structure):
    _fields_ = [
        ('Version', ctypes.c_ulong),
            ('EnableProperty', ctypes.c_ulong),
            ('ControlFlags', ctypes.c_ulong),
            ('SourceId', GUID),
            ('EnableFilterDesc', ctypes.POINTER(EVENT_FILTER_DESCRIPTOR)),
            ('FilterDescCount', ctypes.c_ulong)
    ]


EnableTraceEx2 = advapi32.EnableTraceEx2
EnableTraceEx2.argtypes = [
    TRACEHANDLE,                                # TraceHandle (c_uint64)
    ctypes.POINTER(GUID),                       # ProviderId
    ctypes.c_ulong,                             # ControlCode
    ctypes.c_char,                              # Level
    ctypes.c_ulonglong,                         # MatchAnyKeyword
    ctypes.c_ulonglong,                         # MatchAllKeyword
    ctypes.c_ulong,                             # Timeout
    ctypes.POINTER(ENABLE_TRACE_PARAMETERS)]    # PENABLE_TRACE_PARAMETERS (optional) -> None or pointer
EnableTraceEx2.restype = ctypes.c_ulong


# Define the function prototype
QueryAllTraces = advapi32.QueryAllTracesW
QueryAllTraces.argtypes = [
    ctypes.POINTER(ctypes.POINTER(EVENT_TRACE_PROPERTIES)),
    wintypes.ULONG,
    ctypes.POINTER(wintypes.ULONG)
]
QueryAllTraces.restype = wintypes.ULONG

OpenTrace = advapi32.OpenTraceW
OpenTrace.argtypes = [ctypes.POINTER(EVENT_TRACE_LOGFILE)]
OpenTrace.restype = wintypes.ULONG

ProcessTrace = advapi32.ProcessTrace
ProcessTrace.argtypes = [
    ctypes.POINTER(ctypes.c_uint64),  # pointer to array of 64-bit handles
    wintypes.ULONG,     # handle count
    ctypes.c_void_p,           # LPFILETIME (start)
    ctypes.c_void_p            # LPFILETIME (end)
]
ProcessTrace.restype  = wintypes.ULONG

CloseTrace = advapi32.CloseTrace
CloseTrace.argtypes = [wintypes.ULONG]
CloseTrace.restype = wintypes.ULONG

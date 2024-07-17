import ctypes
from ctypes import wintypes
from ctypes.wintypes import ULONG


# Constants
EVENT_TRACE_CONTROL_STOP = 1
WNODE_FLAG_TRACED_GUID = 0x00020000

MAXIMUM_LOGGERS = 64


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


# Define EVENT_TRACE_PROPERTIES structure
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
        ("LoggerNameOffset", wintypes.ULONG),
        # Allocate space for the names at the end of the structure
        ("_LoggerName", wintypes.WCHAR * 1024),
        ("_LogFileName", wintypes.WCHAR * 1024)
    ]


# Define the EVENT_TRACE_LOGFILE structure
class EVENT_TRACE_LOGFILE(ctypes.Structure):
    _fields_ = [
        ("LogFileName", wintypes.LPWSTR),
        ("LoggerName", wintypes.LPWSTR),
        ("CurrentTime", wintypes.LARGE_INTEGER),
        ("BuffersRead", wintypes.ULONG),
        ("ProcessTraceMode", wintypes.ULONG),
        ("EventRecordCallback", wintypes.LPVOID),
        ("BufferSize", wintypes.ULONG),
        ("Filled", wintypes.ULONG),
        ("EventsLost", wintypes.ULONG),
        ("BuffersLost", wintypes.ULONG),
        ("RealTimeBuffersLost", wintypes.ULONG),
        ("LogBuffersLost", wintypes.ULONG),
        ("BuffersWritten", wintypes.ULONG),
        ("LogFileMode", wintypes.ULONG),
        ("IsKernelTrace", wintypes.ULONG),
        ("Context", wintypes.ULONG)  # Placeholder for context pointer
    ]


# Define the EVENT_TRACE_HEADER structure
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


# Define the EVENT_RECORD structure
class EVENT_RECORD(ctypes.Structure):
    _fields_ = [
        ("EventHeader", EVENT_TRACE_HEADER),
        ("BufferContext", wintypes.ULONG),
        ("ExtendedDataCount", wintypes.USHORT),
        ("UserDataLength", wintypes.USHORT),
        ("ExtendedData", wintypes.LPVOID),
        ("UserData", wintypes.LPVOID),
        ("UserContext", wintypes.LPVOID)
    ]


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
advapi32 = ctypes.WinDLL('advapi32')
tdh = ctypes.windll.tdh

# Define necessary TDH functions
tdh.TdhEnumerateProviders.argtypes = [ctypes.POINTER(PROVIDER_ENUMERATION_INFO), ctypes.POINTER(ULONG)]
tdh.TdhEnumerateProviders.restype = ULONG


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
ProcessTrace.argtypes = [ctypes.POINTER(wintypes.ULONG), wintypes.ULONG, wintypes.LARGE_INTEGER, wintypes.LARGE_INTEGER]
ProcessTrace.restype = wintypes.ULONG

CloseTrace = advapi32.CloseTrace
CloseTrace.argtypes = [wintypes.ULONG]
CloseTrace.restype = wintypes.ULONG

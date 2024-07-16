import ctypes
from ctypes import wintypes
from ctypes.wintypes import ULONG


# Constants
EVENT_TRACE_CONTROL_STOP = 1
WNODE_FLAG_TRACED_GUID = 0x00020000

MAXIMUM_LOGGERS = 64


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

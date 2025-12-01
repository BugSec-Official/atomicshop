#include <windows.h>
#include <psapi.h>
#include <tchar.h>
#include <iostream>
#include <tlhelp32.h>
#include <atomic>

std::atomic<bool> cancelRequested(false);

typedef LONG NTSTATUS;
typedef NTSTATUS (*PFN_NT_QUERY_INFORMATION_PROCESS)(HANDLE, UINT, PVOID, ULONG, PULONG);

#define STATUS_SUCCESS ((NTSTATUS)0x00000000L)

typedef struct _UNICODE_STRING {
    USHORT Length;
    USHORT MaximumLength;
    PWSTR Buffer;
} UNICODE_STRING;

typedef struct _RTL_USER_PROCESS_PARAMETERS {
    BYTE Reserved1[16];
    PVOID Reserved2[10];
    UNICODE_STRING ImagePathName;
    UNICODE_STRING CommandLine;
} RTL_USER_PROCESS_PARAMETERS;

typedef struct _PEB {
    BYTE Reserved1[2];
    BYTE BeingDebugged;
    BYTE Reserved2[21];
    PVOID LoaderData;
    RTL_USER_PROCESS_PARAMETERS* ProcessParameters;
    // ... rest of the structure
} PEB;

typedef struct _PROCESS_BASIC_INFORMATION {
    PVOID Reserved1;
    PEB* PebBaseAddress;
    PVOID Reserved2[2];
    ULONG_PTR UniqueProcessId;
    PVOID Reserved3;
} PROCESS_BASIC_INFORMATION;

bool EnableDebugPrivilege() {
    HANDLE hToken;
    LUID luid;
    TOKEN_PRIVILEGES tkp;

    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, &hToken))
        return false;

    if (!LookupPrivilegeValue(NULL, SE_DEBUG_NAME, &luid))
        return false;

    tkp.PrivilegeCount = 1;
    tkp.Privileges[0].Luid = luid;
    tkp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED;

    if (!AdjustTokenPrivileges(hToken, false, &tkp, sizeof(tkp), NULL, NULL))
        return false;

    if (GetLastError() == ERROR_NOT_ALL_ASSIGNED)
        return false;

    CloseHandle(hToken);
    return true;
}

bool GetProcessCommandLine(DWORD dwPid, wchar_t** ppszCmdLine, wchar_t* szProcessName, DWORD dwNameSize) {
    HANDLE hProcess = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, FALSE, dwPid);
    if (hProcess == NULL)
        return false;

    // Get the process name
    if (!GetModuleBaseNameW(hProcess, NULL, szProcessName, dwNameSize)) {
        CloseHandle(hProcess);
        return false;
    }

    HMODULE hNtDll = GetModuleHandleW(L"ntdll.dll");
    if (hNtDll == NULL) {
        CloseHandle(hProcess);
        return false;
    }

    PFN_NT_QUERY_INFORMATION_PROCESS pfnNtQueryInformationProcess = (PFN_NT_QUERY_INFORMATION_PROCESS)GetProcAddress(hNtDll, "NtQueryInformationProcess");
    if (pfnNtQueryInformationProcess == NULL) {
        CloseHandle(hProcess);
        return false;
    }

    PROCESS_BASIC_INFORMATION pbi;
    ULONG ulSize;
    NTSTATUS status = pfnNtQueryInformationProcess(hProcess, 0, &pbi, sizeof(pbi), &ulSize);
    if (status != STATUS_SUCCESS) {
        CloseHandle(hProcess);
        return false;
    }

    PEB peb;
    if (!ReadProcessMemory(hProcess, pbi.PebBaseAddress, &peb, sizeof(peb), NULL)) {
        CloseHandle(hProcess);
        return false;
    }

    RTL_USER_PROCESS_PARAMETERS upp;
    if (!ReadProcessMemory(hProcess, peb.ProcessParameters, &upp, sizeof(upp), NULL)) {
        CloseHandle(hProcess);
        return false;
    }

    *ppszCmdLine = new wchar_t[upp.CommandLine.Length / sizeof(wchar_t) + 1];
    if (!ReadProcessMemory(hProcess, upp.CommandLine.Buffer, *ppszCmdLine, upp.CommandLine.Length, NULL)) {
        delete[] * ppszCmdLine;
        CloseHandle(hProcess);
        return false;
    }

    (*ppszCmdLine)[upp.CommandLine.Length / sizeof(wchar_t)] = L'\0';
    CloseHandle(hProcess);
    return true;
}

typedef void(*CallbackFunc)(DWORD pid, wchar_t* process_name, wchar_t* cmdline);

extern "C" __declspec(dllexport) void RequestCancellation() {
    cancelRequested.store(true);
}

extern "C" __declspec(dllexport) void GetProcessDetails(CallbackFunc callback) {
    if (!EnableDebugPrivilege()) {
        std::wcout << L"Failed to enable debug privilege." << std::endl;
        return;
    }

    // This function fetches PID Process name and it doesn't need any privileges or Debug Priveleges.
    HANDLE hSnap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hSnap == INVALID_HANDLE_VALUE) {
        std::wcout << L"Failed to create snapshot." << std::endl;
        return;
    }

    PROCESSENTRY32W pe32;
    pe32.dwSize = sizeof(PROCESSENTRY32W);
    if (!Process32FirstW(hSnap, &pe32)) {
		DWORD error = GetLastError();
		std::wcout << L"Error code: " << error << std::endl;
        CloseHandle(hSnap);
        std::wcout << L"Failed to get first process from snapshot." << std::endl;
        return;
    }

    do {
        wchar_t* pszCmdLine = NULL;
        wchar_t szProcessName[MAX_PATH] = L"<unknown>";
        wcsncpy_s(szProcessName, MAX_PATH, pe32.szExeFile, _TRUNCATE);
        
		// Process Command Line fetch from PID is much more complicated and needs Debug Priveleges and user to run it as admin.
        if (GetProcessCommandLine(pe32.th32ProcessID, &pszCmdLine, szProcessName, sizeof(szProcessName) / sizeof(wchar_t))) {
            callback(pe32.th32ProcessID, szProcessName, pszCmdLine);
            delete[] pszCmdLine;
        } else {
            callback(pe32.th32ProcessID, szProcessName, NULL);
        }
    } while (Process32NextW(hSnap, &pe32) && !cancelRequested.load());

    CloseHandle(hSnap);
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved) {
    switch (ul_reason_for_call) {
    case DLL_PROCESS_ATTACH:
    case DLL_THREAD_ATTACH:
    case DLL_THREAD_DETACH:
    case DLL_PROCESS_DETACH:
        break;
    }
    return TRUE;
}

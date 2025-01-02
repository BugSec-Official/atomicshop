import os
import ctypes
import pefile


def get_file_properties(file_path: str) -> dict:
    """
    Retrieve file version properties using ctypes.

    :param file_path: Full path to the file.
    :return: Dictionary with file properties.
    """

    def query_value(name):
        r = ctypes.c_void_p()
        l = ctypes.c_uint()
        ctypes.windll.version.VerQueryValueW(
            res, f"\\StringFileInfo\\040904b0\\{name}", ctypes.byref(r), ctypes.byref(l))
        return ctypes.wstring_at(r) if r.value else "N/A"

    properties = {
        "FileDescription": "N/A",
        "FileVersion": "N/A",
        "ProductName": "N/A",
        "ProductVersion": "N/A",
    }

    if not os.path.isfile(file_path):
        return properties

    # Load version information
    size = ctypes.windll.version.GetFileVersionInfoSizeW(file_path, None)
    if size == 0:
        return properties

    res = ctypes.create_string_buffer(size)
    ctypes.windll.version.GetFileVersionInfoW(file_path, None, size, res)

    properties["FileDescription"] = query_value("FileDescription")
    properties["FileVersion"] = query_value("FileVersion")
    properties["ProductName"] = query_value("ProductName")
    properties["ProductVersion"] = query_value("ProductVersion")

    # Fallback to pefile if ctypes fails or returns, pefile is much slower but more reliable, so we only use it as a fallback.
    if properties["FileDescription"] == "N/A" or properties["FileVersion"] == "N/A":
        pe = pefile.PE(file_path)
        version_info = pe.VS_FIXEDFILEINFO
        if version_info:
            # If version_info is a list, take the first valid entry
            if isinstance(version_info, list):
                version_info = version_info[0]

            properties["FileVersion"] = f"{version_info.FileVersionMS >> 16}.{version_info.FileVersionMS & 0xFFFF}.{version_info.FileVersionLS >> 16}.{version_info.FileVersionLS & 0xFFFF}"
        # Attempt to get additional metadata
        for entry in pe.FileInfo or []:
            for structure in entry:
                if hasattr(structure, "StringTable"):
                    for string_table in structure.StringTable:
                        for key, value in string_table.entries.items():
                            if key == b"FileDescription":
                                properties["FileDescription"] = value.decode("utf-8", errors="ignore")
                            elif key == b"ProductName":
                                properties["ProductName"] = value.decode("utf-8", errors="ignore")
                            elif key == b"ProductVersion":
                                properties["ProductVersion"] = value.decode("utf-8", errors="ignore")

    return properties

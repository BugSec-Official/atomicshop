import os
import ctypes


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

    return properties

from io import BytesIO
from typing import Union

import py7zr


def is_7z(file_object: Union[str, bytes]) -> bool:
    """
    Function checks if the file is a 7z file.
    :param file_object: can be two types:
        string, full path to the file.
        bytes or BytesIO, the bytes of the file.
    :return: boolean.
    """

    try:
        if isinstance(file_object, bytes):
            with BytesIO(file_object) as file_object:
                with py7zr.SevenZipFile(file_object) as archive:
                    archive.testzip()
                    return True
        elif isinstance(file_object, str):
            with py7zr.SevenZipFile(file_object) as archive:
                archive.testzip()
                return True
    except py7zr.Bad7zFile:
        return False
    # For some reason there are files that return this exception instead of Bad7zFile.
    except OSError as e:
        if e.args[0] == 22:
            return False


def _is_7z_magic_number(data):
    # Check if the data is at least 6 bytes long
    if len(data) < 6:
        return False

    # 7z file signature (magic number)
    # The signature is '7z' followed by 'BCAF271C'
    seven_z_signature = b'7z\xBC\xAF\x27\x1C'

    # Compare the first 6 bytes of the data with the 7z signature
    return data.startswith(seven_z_signature)

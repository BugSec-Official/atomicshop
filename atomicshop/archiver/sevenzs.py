from io import BytesIO
from typing import Union

import py7zr


def is_7z_magic_number(
        file_object: Union[str, bytes]
) -> bool:
    """
    Function checks if the file is a 7z file, by checking the magic number.

    :param file_object: can be two types:
        string, full path to the file.
        bytes or BytesIO, the bytes of the file.
    :return: boolean.
    """

    if isinstance(file_object, str):
        with open(file_object, 'rb') as file:
            data = file.read(6)
    elif isinstance(file_object, bytes):
        data = file_object
    else:
        raise TypeError(f'The file_object must be a string or bytes, not {type(file_object)}')

    # Check if the data is at least 6 bytes long
    if len(data) < 6:
        return False

    # 7z file signature (magic number)
    # The signature is '7z' followed by 'BCAF271C'
    seven_z_signature = b'7z\xBC\xAF\x27\x1C'

    # Compare the first 6 bytes of the data with the 7z signature
    result = data.startswith(seven_z_signature)

    return result


def _is_7z(file_object: Union[str, bytes]) -> bool:
    """
    THIS IS ONLY FOR THE REFERENCE.

    Used to use this function since it raised 'py7zr.Bad7zFile' if the file was not a 7z file.
    The problem that 'SevenZipFile.testzip()' checks archived files CRCs and returns the first bad file:
    https://py7zr.readthedocs.io/en/latest/api.html#py7zr.SevenZipFile.testzip
    The problem is when the file IS 7z file, but there can be other problems with the file, it can raise a RuntimeError.
    So, better use the 'is_7z_magic_number' function.

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

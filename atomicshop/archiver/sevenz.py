import py7zr


def is_7z(file_path: str) -> bool:
    """
    Function checks if the file is a 7z file.
    :param file_path: string, full path to the file.
    :return: boolean.
    """

    try:
        with py7zr.SevenZipFile(file_path) as archive:
            archive.testzip()
            return True
    except py7zr.Bad7zFile:
        return False

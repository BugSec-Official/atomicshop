from ... file_io import file_io
from ... import filesystem, hashing


def get_uid_from_file(file_binary: bytes = None, file_path: str = None, sha256_hash: str = None) -> str:
    """
    Get FACT UID from firmware binary file.
    :param file_binary: bytes, firmware binary file.
    :param file_path: string, path to firmware binary file.
    :param sha256_hash: string, sha256 hash of firmware binary file. If not specified, it will be calculated.
    :return: string, FACT UID.
    """

    if file_binary is None and file_path is None:
        raise ValueError('Either file_binary or file_path must be specified.')

    if file_path:
        file_binary = file_io.read_file(file_path, file_mode='rb')

    if sha256_hash is None:
        sha256_hash = hashing.hash_bytes(file_binary, hash_algo='sha256')

    binary_length: str = str(len(file_binary))
    return f'{sha256_hash}_{binary_length}'


def get_file_data(directory_path: str, firmwares: list = None):
    """
    Get file hashes, binaries and UIDs from the specified directory.
    :param directory_path: string, path to directory with firmware binary files.
    :param firmwares: list, list of dictionaries with firmware file paths and hashes.
    :return:
    """

    if not firmwares:
        firmwares: list = filesystem.get_paths_from_directory(
            directory_path, get_file=True, recursive=False, add_file_binary=True, add_file_hash=True)

    # Add UIDs to the list.
    final_firmwares: list = []
    for firmware in firmwares:
        uid = get_uid_from_file(file_binary=firmware.binary, sha256_hash=firmware.hash)
        final_firmwares.append({
            'path': firmware.path,
            'hash': firmware.hash,
            'binary': firmware.binary,
            'uid': uid
        })

    return final_firmwares

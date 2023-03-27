# v1.0.2 - 21.03.2023 18:30
import shlex

from .. import process


def extract_archive_with_tar(file_path: str, target_directory: str) -> None:
    """
    Function extracts the archive to target directory.

    :param file_path: Full file path to archived file to extract.
    :param target_directory: The directory on the filesystem to extract the file to.
    :return: None
    """

    # -v: Verbose, shows list of extracted files.
    # -C: Output directory.
    cmd: str = f'tar -xzvf "{file_path}" -C "{target_directory}"'
    cmd_list: list = shlex.split(cmd)

    output_list = process.execute_with_live_output(cmd=cmd_list)

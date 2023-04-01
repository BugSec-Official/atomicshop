# v1.0.2 - 21.03.2023 13:40
import sys
import shlex

from .. import process
from .. import web


def download_file_with_curl(file_url: str, target_directory: str) -> None:
    """
    The function receives url and target filesystem directory to download the file.

    :param file_url: full URL to download the file.
    :param target_directory: The directory on the filesystem to save the file to.
    """

    # Get only the filename from URL.
    file_name, file_path = web.get_filename_and_target_filepath(
        file_url=file_url, target_directory=target_directory)

    cmd: str = f'curl -L {file_url} --output "{file_path}"'
    cmd_list: list = shlex.split(cmd)

    output_list: list = process.execute_with_live_output(cmd=cmd_list)
    # If there was error in curl.
    if 'curl: ' in output_list[-1]:
        print('Curl error. Exiting...')
        sys.exit()

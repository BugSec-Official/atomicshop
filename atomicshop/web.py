import os
import urllib.request

from .print_api import print_api
from .archiver import extract_archive_with_zipfile
from .filesystem import remove_file
from .urls import url_parser


# https://www.useragents.me/
# https://user-agents.net/
USER_AGENTS = {
    'Chrome_111.0.0_Windows_10-11_x64':
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36'
}


def is_status_ok(status_code: int, **kwargs) -> bool:
    """
    Function checks is HTTP response status is 200 OK. If OK - returns True, otherwise False.
    :param status_code: status code integer.
    :return: Boolean.
    """

    if status_code != 200:
        print_api(f'URL Error, status code: {str(status_code)}', error_type=True, **kwargs)
        return False
    else:
        print_api('URL Status: 200 OK', color="green", **kwargs)
        return True


def get_filename_from_url(file_url: str):
    # Parse the url.
    url_parts = url_parser(file_url)
    # File name is the last directory.
    file_name: str = url_parts['directories'][-1]

    return file_name


def get_page_bytes(url: str, user_agent: str = str(), default_user_agent: bool = False) -> bytes:
    """
    Function returns the page content from the given URL.
    Returns only the byte response.

    :param url: string, full URL.
    :param user_agent: string, user agent to use when downloading the page.
    :param default_user_agent: boolean, if True, the default user agent will be used.
    :return: string, page content.
    """

    if not default_user_agent and not user_agent:
        raise ValueError('ERROR: No [user_agent] specified and [default_user_agent] usage is [False].')

    if default_user_agent:
        user_agent = USER_AGENTS['Chrome_111.0.0_Windows_10-11_x64']

    # Create a 'Request' object with the URL and user agent.
    request = urllib.request.Request(url, headers={'User-Agent': user_agent})

    # Open the URL and read the page content.
    response = urllib.request.urlopen(request).read()

    return response


def download(file_url: str, target_directory: str, file_name: str = str(), **kwargs) -> str:
    """
    The function receives url and target filesystem directory to download the file.

    :param file_url: full URL to download the file.
    :param target_directory: The directory on the filesystem to save the file to.
    :param file_name: string, file name (example: file.zip) that you want the downloaded file to be saved as.
        If not specified, the default filename from 'file_url' will be used.
    :return: string, full file path of downloaded file. If download failed, 'None' will be returned.
    """

    def print_to_console(print_end=None):
        if file_size_bytes_int:
            print_api(
                f'Downloaded bytes: {aggregated_bytes_int} / {file_size_bytes_int}', print_end=print_end, **kwargs)
        else:
            print_api(f'Downloaded bytes: {aggregated_bytes_int}', print_end=print_end, **kwargs)

    # Size of the buffer to read each time from url.
    buffer_size: int = 4096

    # If 'file_name' wasn't specified, we will extract it from 'file_url'.
    if not file_name:
        # Get only the filename from URL.
        file_name = get_filename_from_url(file_url=file_url)

    # Build full path to file.
    file_path: str = f'{target_directory}{os.sep}{file_name}'

    print_api(f'Downloading: {file_url}', **kwargs)

    # In order to use 'urllib.request', it is not enough to 'import urllib', you need to 'import urllib.request'.
    # Open the URL for data gathering.
    file_to_download = urllib.request.urlopen(file_url)

    # Check status of url.
    if not is_status_ok(status_code=file_to_download.status, **kwargs):
        return None

    # Get file size. For some reason doesn't show for GitHub branch downloads.
    file_size_bytes_int: int = int(file_to_download.headers['Content-Length'])

    # Open the target file for writing in binary mode.
    with open(file_path, 'wb') as output:
        # We can read the whole file at once. The problem is that the whole file will be in memory, which isn't
        # good for large files / systems with small ram. So, we'll read the file in buffers.
        # Initialize aggregated_bytes_int object.
        aggregated_bytes_int: int = int()
        while True:
            # Data to get each time.
            data = file_to_download.read(buffer_size)
            # If there's no data, the file has been finished downloading, and we can stop the loop.
            if data:
                # Add the buffer to the file that we're writing to.
                output.write(data)
                # Add the gathered data length to 'aggregated_bytes_int' for printing.
                aggregated_bytes_int = aggregated_bytes_int + len(data)

                print_to_console(print_end='\r')
            else:
                print_to_console()
                break
    if aggregated_bytes_int == file_size_bytes_int:
        print_api(f'Successfully Downloaded to: {file_path}', color="green", **kwargs)
    else:
        message = f'Download failed: {aggregated_bytes_int} / {file_size_bytes_int}. File: {file_path}'
        print_api(
            message, error_type=True, color="red", **kwargs)

    return file_path


def download_and_extract_file(
        file_url: str, target_directory: str, file_name: str = str(), archive_remove_first_directory: bool = False,
        **kwargs):
    """
    This function will download the branch file from GitHub, extract the file and remove the file, leaving
    only the extracted folder.

    :param file_url: full URL to download the file.
    :param file_name: string, filename with extension that the url will be saved as on the filesystem.
        Default is empty. If it is empty, then the filename will be extracted from 'file_url'.
    :param target_directory: string, target directory where to save the file.
    :param archive_remove_first_directory: boolean, sets if archive extract function will extract the archive without
        first directory in the archive. Check reference in the 'extract_archive_with_zipfile' function.
    :return:
    """

    # Download the repo to current working directory and return full file path of downloaded file.
    file_path = download(
        file_url=file_url, target_directory=target_directory, file_name=file_name, **kwargs)

    # Extract the archive and remove the first directory.
    extract_archive_with_zipfile(
        archive_path=f'{file_path}', extract_directory=target_directory,
        remove_first_directory=archive_remove_first_directory, **kwargs)

    # Remove the archive file.
    remove_file(file_path=f'{file_path}', **kwargs)

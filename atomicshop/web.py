import os
import urllib.request

from .print_api import print_api
from .archiver import zips
from .urls import url_parser
from .file_io import file_io
from .wrappers.playwrightw import scenarios
from . import filesystem


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


def get_page_bytes(
        url: str,
        user_agent: str = None,
        chrome_user_agent: bool = False,
        path: str = None,
        print_kwargs: dict = None) -> bytes:
    """
    Function returns the page content from the given URL.
    Returns only the byte response.

    :param url: string, full URL.
    :param user_agent: string, user agent to use when downloading the page.
    :param chrome_user_agent: boolean, if True, the Chrome user agent will be used: 'Chrome_111.0.0_Windows_10-11_x64'.
    :param path: string, path to save the downloaded file to. If None, the file will not be saved to disk.
    :param print_kwargs: dict, that contains all the arguments for 'print_api' function.

    :return: bytes, page content.
    """

    if not print_kwargs:
        print_kwargs = dict()

    if chrome_user_agent and user_agent:
        raise ValueError('ERROR: [user_agent] specified and [chrome_user_agent] usage is [True]. Choose one.')

    if chrome_user_agent:
        user_agent = USER_AGENTS['Chrome_111.0.0_Windows_10-11_x64']

    if user_agent:
        # Create a 'Request' object with the URL and user agent.
        request = urllib.request.Request(url, headers={'User-Agent': user_agent})
    else:
        # Create a 'Request' object with the URL only.
        request = urllib.request.Request(url)

    # Open the URL and read the page content.
    response = urllib.request.urlopen(request).read()

    # Save the file to disk, if path was specified.
    if path:
        file_io.write_file(content=response, file_path=path, file_mode='wb', **print_kwargs)

    return response


def get_page_content(
        url: str, get_method: str = 'urllib', path: str = None,
        playwright_pdf_format: str = 'A4',
        playwright_html_txt_convert_to_bytes: bool = True,
        print_kwargs: dict = None) -> any:
    """
    Function returns the page content from the given URL.

    :param url: string, full URL.
    :param get_method: string, method to use to get the page content.
        'urllib': uses requests library. For static HTML pages without JavaScript. Returns HTML bytes.
        'playwright_*': uses playwright library, headless. For dynamic HTML pages with JavaScript.
            'playwright_html': For dynamic HTML pages with JavaScript. Returns HTML.
            'playwright_txt': For dynamic HTML pages with JavaScript. Returns Text from the above fetched HTML.
            'playwright_pdf': For dynamic HTML pages with JavaScript. Returns PDF.
            'playwright_pdf_*': For dynamic HTML pages with JavaScript. Returns PDF.
                Example: 'playwright_pdf_A0'.
            'playwright_png': For dynamic HTML pages with JavaScript. Returns PNG.
            'playwright_jpeg': For dynamic HTML pages with JavaScript. Returns JPEG.
    :param path: string, path to save the downloaded file to. If None, the file will not be saved to disk.
    :param playwright_pdf_format: string, pdf format, applicable only if 'get_method=playwright_pdf'. Default is 'A4'.
    :param playwright_html_txt_convert_to_bytes: boolean, applicable only if 'get_method=playwright_html'
        or 'get_method=playwright_txt'. Default is True.
    :param print_kwargs: dict, that contains all the arguments for 'print_api' function.

    :return: any, type depends on the method, return page content.
    """

    result = None
    if get_method == 'urllib':
        # Get HTML from url, return bytes.
        result = get_page_bytes(url=url, chrome_user_agent=True, path=path, print_kwargs=print_kwargs)
    elif get_method == 'playwright_html':
        result = scenarios.get_page_content_in_thread(
            url=url, page_format='html', path=path, html_txt_convert_to_bytes=playwright_html_txt_convert_to_bytes,
            print_kwargs=print_kwargs)
    elif get_method == 'playwright_txt':
        result = scenarios.get_page_content_in_thread(
            url=url, page_format='txt', path=path, html_txt_convert_to_bytes=playwright_html_txt_convert_to_bytes,
            print_kwargs=print_kwargs)
    elif 'playwright_pdf' in get_method:
        # Get all the parts of the method in case there is a Page Layout passed.
        string_parts = get_method.split('_')
        # If there is a Page Layout passed, get it.
        # Example: 'playwright_pdf_A0'.
        if len(string_parts) > 2:
            playwright_pdf_format = string_parts[2]
        result = scenarios.get_page_content_in_thread(
            url=url, page_format='pdf', path=path, pdf_format=playwright_pdf_format, print_kwargs=print_kwargs)
    elif get_method == 'playwright_png':
        result = scenarios.get_page_content_in_thread(url=url, page_format='png', path=path, print_kwargs=print_kwargs)
    elif get_method == 'playwright_jpeg':
        result = scenarios.get_page_content_in_thread(url=url, page_format='jpeg', path=path, print_kwargs=print_kwargs)

    return result


def download(file_url: str, target_directory: str, file_name: str = None, **kwargs) -> str:
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
    print_api(f'To: {file_path}', **kwargs)

    # In order to use 'urllib.request', it is not enough to 'import urllib', you need to 'import urllib.request'.
    # Open the URL for data gathering.
    file_to_download = urllib.request.urlopen(file_url)

    # Check status of url.
    if not is_status_ok(status_code=file_to_download.status, **kwargs):
        return None

    file_size_bytes_int: int = None
    # Get file size. For some reason doesn't show for GitHub branch downloads.
    if file_to_download.headers['Content-Length']:
        file_size_bytes_int = int(file_to_download.headers['Content-Length'])

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
    zips.extract_archive_with_zipfile(
        archive_path=f'{file_path}', extract_directory=target_directory,
        remove_first_directory=archive_remove_first_directory, **kwargs)

    # Remove the archive file.
    filesystem.remove_file(file_path=f'{file_path}', **kwargs)

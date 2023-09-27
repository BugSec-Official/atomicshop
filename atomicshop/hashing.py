import hashlib
import sys

from . import web


def hash_bytes(bytes_object: bytes, hash_algo: str = 'sha256'):
    # Equivalent to sha256 example: hashlib.sha256(bytes_object).hexdigest()
    return getattr(hashlib, hash_algo)(bytes_object).hexdigest()


def hash_url(
        url: str,
        get_method: str = 'urllib',
        path: str = None,
        hash_algo: str = 'sha256',
        print_kwargs: dict = None
) -> str:
    """
    The function will return hash of the page content from URL with specified algorithm.

    :param url: string, full URL.
    :param get_method: string, method to use to get the page content.
        'urllib': uses requests library. For static HTML pages without JavaScript. Returns HTML bytes.
        'playwright_*': uses playwright library, headless. For dynamic HTML pages with JavaScript.
            'playwright_html': Gets HTML.
            'playwright_pdf': Gets PDF.
            'playwright_png': Gets PNG.
            'playwright_jpeg': Gets JPEG.
    :param path: string, path to save the downloaded file to. If None, the file will not be saved to disk.
    :param hash_algo: string, file hashing algorithm. Default is 'sha256'.
    :param print_kwargs: dict, that contains all the arguments for 'print_api' function.

    :return: string, hash of the page content.
    """

    # Get page content from URL.
    response = web.get_page_content(url, get_method=get_method, path=path, print_kwargs=print_kwargs)

    if response:
        # Hash the content.
        return hash_bytes(response, hash_algo)
    else:
        raise ValueError(f'Response returned empty from URL, nothing to hash')


def hash_file(file_path: str, hash_algo: str = 'sha256', block_size: int = 1024):
    """
    The function will return hash of the file with specified algorithm.

    :param file_path: string, full file path to file to hash.
    :param hash_algo: string, file hashing algorithm. Tested:
        md5, sha256, sha1
    :param block_size: integer, of block size in bytes that will be hashed at a time.
    """

    # Function from python 3.8 and above because of 'assignment expression'.
    if (3, 8) <= sys.version_info < (3, 11):
        # Example for type specific: hashlib.sha256()
        hashlib_object = getattr(hashlib, hash_algo)()
        bytearray_empty = bytearray(128*block_size)
        memoryview_object = memoryview(bytearray_empty)
        with open(file_path, 'rb', buffering=0) as file_object:
            # noinspection PyUnresolvedReferences
            while n := file_object.readinto(memoryview_object):
                hashlib_object.update(memoryview_object[:n])
        return hashlib_object.hexdigest()
    # From python version 3.11 there is new easier function for that.
    elif sys.version_info >= (3, 11):
        with open(file_path, 'rb', buffering=0) as file_object:
            return hashlib.file_digest(file_object, hash_algo).hexdigest()

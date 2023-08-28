from ... import web, hashing


def get_url(
        url: str,
        get_method: str = 'urllib',
        path: str = None) -> str:
    """
    The function will check url page for change by hashing it and comparing the hash.

    :param url: string, full URL.
    :param get_method: string, method to use to get the page content.
        'urllib': uses requests library. For static HTML pages without JavaScript. Returns HTML bytes.
        'playwright_*': uses playwright library, headless. For dynamic HTML pages with JavaScript.
            'playwright_html': For dynamic HTML pages with JavaScript. Returns HTML.
            'playwright_pdf': For dynamic HTML pages with JavaScript. Returns PDF.
            'playwright_png': For dynamic HTML pages with JavaScript. Returns PNG.
            'playwright_jpeg': For dynamic HTML pages with JavaScript. Returns JPEG.
    :param path: string, path to save the downloaded file to. If None, the file will not be saved to disk.

    :return: string, hash of the page content.
    """

    # Get page content from URL.
    response = web.get_page_content(url, get_method=get_method, path=path)

    if get_method == 'urllib':
        # Hash HTML.
        return hashing.hash_bytes(response)

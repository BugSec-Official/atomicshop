from urllib.parse import urlparse
import re


def url_parser(url):
    # https://practicaldatascience.co.uk/data-science/how-to-parse-url-structures-using-python
    parts = urlparse(url)
    directories = parts.path.strip('/').split('/')
    queries = parts.query.strip('&').split('&')

    elements = {
        'scheme': parts.scheme,
        'netloc': parts.netloc,
        'path': parts.path,
        'params': parts.params,
        'query': parts.query,
        'fragment': parts.fragment,
        'directories': directories,
        'queries': queries,
    }

    return elements


def is_valid_url(url):
    """
    Check if a URL is valid.
    :param url:
    :return:
    """

    parsed = urlparse(url)
    return all([parsed.scheme, parsed.netloc])


def find_urls_in_text(text: str) -> list[str]:
    """
    Find URLs in text

    :param text: string, text to search for URLs.
    :return: list of strings, URLs found in text.
    """

    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    urls = url_pattern.findall(text)

    # Filter URLs to remove common false positives
    cleaned_urls = []
    for u in urls:
        cleaned_url = u.strip('",.:;!?)(')
        if is_valid_url(cleaned_url):
            cleaned_urls.append(cleaned_url)

    return cleaned_urls

# v1.0.0
# Basic imports.
from urllib.parse import urlparse


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

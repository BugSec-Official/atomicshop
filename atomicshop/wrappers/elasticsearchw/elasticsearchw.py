from elasticsearch import Elasticsearch
from datetime import datetime

from . import config_basic
from ...basics import dicts


ELASTIC_WRAPPER = None


def get_elastic_wrapper(url: str = None, overwrite: bool = False):
    """
    The function initializes the Elasticsearch wrapper.

    :param url: str, the url of the Elasticsearch server. If None, the default url is used: http://localhost:9200
    :param overwrite: bool, if True, the wrapper is reinitialized even if it is already initialized.
    :return: Elasticsearch, the Elasticsearch wrapper.

    Usage:
        elastic_wrapper = get_elastic_wrapper()
    or after you initialize it once, you can use it like:
        atomicshop.wrappers.elasticsearchw.elasticsearchw.ELASTIC_WRAPPER
    """

    # If no url is provided, use the default url.
    if url is None:
        url = config_basic.DEFAULT_URL

    # Get the global variable.
    global ELASTIC_WRAPPER
    # If the wrapper is not initialized, initialize it.
    if ELASTIC_WRAPPER is None:
        ELASTIC_WRAPPER = Elasticsearch([url])
    # If the wrapper is already initialized, check if it should be overwritten.
    else:
        if overwrite:
            ELASTIC_WRAPPER = Elasticsearch([url])

    return ELASTIC_WRAPPER


def test_connection(elastic_wrapper: Elasticsearch = None):
    """
    The function tests the connection to the Elasticsearch server.

    :param elastic_wrapper: Elasticsearch, the Elasticsearch wrapper.
    :return: bool, True if the connection is successful, False otherwise.

    Usage:
        res = test_connection()
    """

    if elastic_wrapper is None:
        elastic_wrapper = get_elastic_wrapper()

    if elastic_wrapper.ping():
        return True
    else:
        return False


def index(
        index_name: str,
        doc: dict,
        doc_id: str = None,
        use_current_timestamp: bool = False,
        convert_mixed_lists_to_strings: bool = False,
        elastic_wrapper: Elasticsearch = None):
    """
    The function indexes a document in the Elasticsearch server.

    :param index_name: str, the name of the index.
    :param doc: dict, the document to be indexed.
    :param doc_id: str, the id of the document. If None, a random id is generated.
        This means that if you index the document with the same id again, the document inside DB will be overwritten.
    :param use_current_timestamp: bool, if True, the current datetime is used as the timestamp of the document.
    :param convert_mixed_lists_to_strings: bool, if True, mixed lists or tuples when entries are strings and integers,
        the integers will be converted to strings.
    :param elastic_wrapper: Elasticsearch, the Elasticsearch wrapper.
    :return: dict, the result of the indexing operation.

    Usage:
        doc = {
            'author': 'test_author',
            'text': 'Some test text',
        }
        res = index(index_name="test_index", doc=doc)
    """

    if elastic_wrapper is None:
        elastic_wrapper = get_elastic_wrapper()

    if use_current_timestamp:
        doc['timestamp'] = datetime.now()

    if convert_mixed_lists_to_strings:
        doc = dicts.convert_int_to_str_in_mixed_lists(doc)

    res = elastic_wrapper.index(index=index_name, body=doc, id=doc_id)

    return res


def search(index_name: str, query: dict, elastic_wrapper: Elasticsearch = None, get_hits_only: bool = True):
    """
    The function searches for documents in the Elasticsearch server.

    :param index_name: str, the name of the index.
    :param query: dict, the query to be used for searching the documents.
    :param elastic_wrapper: Elasticsearch, the Elasticsearch wrapper.
    :param get_hits_only: bool, if True, only the hits are returned.
    :return: dict, the result of the search operation.

    Usage:
        query = {
            "query": {
                "match_all": {}
            }
        }
        res = search(index_name="test_index", query=query)
    """

    if elastic_wrapper is None:
        elastic_wrapper = get_elastic_wrapper()

    res = elastic_wrapper.search(index=index_name, body=query)

    if get_hits_only:
        return get_response_hits(res)
    else:
        return res


def count(index_name: str, query: dict, elastic_wrapper: Elasticsearch = None):
    """
    The function counts the number of documents in the index that match the query.

    :param index_name: str, the name of the index.
    :param query: dict, the query to be used for counting the documents.
    :param elastic_wrapper: Elasticsearch, the Elasticsearch wrapper.
    :return: int, the number of documents that match the query.

    Usage:
        query = {
            "query": {
                "match_all": {}
            }
        }
        res = count(index_name="test_index", query=query)
    """

    if elastic_wrapper is None:
        elastic_wrapper = get_elastic_wrapper()

    res = elastic_wrapper.count(index=index_name, body=query)

    return res['count']


def get_response_hits(response: dict):
    """
    The function returns the 'hits' from the response.

    :param response: dict, the response from the Elasticsearch server.
    :return: list, the hits from the response.

    Usage:
        res = get_response_hits(response)
    """

    return [hit['_source'] for hit in response['hits']['hits']]

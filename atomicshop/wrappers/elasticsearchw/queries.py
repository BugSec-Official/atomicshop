def create_match_all():
    """
    Create a match_all query for Elasticsearch.
    This query will match all the documents in the index.

    :return: dict, the match_all query.
    """

    return {
        "query": {
            "match_all": {}
        }
    }


def create_boolean_filter(field_name: str, value: bool):
    """
    Create a boolean filter for Elasticsearch.
    This filter will filter all the documents that have the field 'field_name' set to True.

    :param field_name: str, the name of the field to filter by.
    :param value: bool, the value of the field to filter by.
    :return: dict, the boolean filter.
    """

    return {
        "query": {
            "bool": {
                "filter": [
                    {"term": {field_name: value}}
                ]
            }
        }
    }


def create_wildcard(field_name: str, search_term: str):
    """
    Create a wildcard query for Elasticsearch.
    This query uses the regular 'field_name' and not the '.keyword' version.
    What this means:
    By default, all the text fields will be processed by the standard analyzer.
    https://www.elastic.co/guide/en/elasticsearch/reference/current/analyzer.html
    https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-standard-analyzer.html
    This means that the text will be lower-cased, and the special characters will be stripped.

    Example: "TEst1-TeSt2" will be processed to ["test1", "test2"].

    To skip using the standard analyzer, we can use the '.keyword' version of the field.

    :param field_name: str, the name of the field to search in.
    :param search_term: str, the search term with the wildcard '*'.
    :return: dict, the wildcard query.
    """

    return {
        "query": {
            "wildcard": {
                field_name: {
                    "value": search_term
                }
            }
        }
    }


def create_wildcard_exact_term(field_name: str, search_term: str):
    """
    Create a wildcard query for Elasticsearch to unprocessed version by the standard analyzer.
    This query uses the '.keyword' version of the field.

    To read about the problem with the standard analyzer, read the docstring of the function 'create_wildcard'.

    :param field_name: str, the name of the field to search in.
    :param search_term: str, the search term with the wildcard '*'.
    :return: dict, the wildcard query.
    """

    return {
        "query": {
            "wildcard": {
                f"{field_name}.keyword": {
                    "value": search_term
                }
            }
        }
    }


def create_pagination(page: int, size: int) -> dict:
    """
    Create the pagination query for Elasticsearch.

    :param page: int, the page number.
    :param size: int, the number of results per page.
    :return: dict, the pagination query.
    """

    # Calculate the "from" parameter for Elasticsearch
    start_from = (page - 1) * size

    # Elasticsearch query
    return {
        "from": start_from,
        "size": size,
        "query": {
            "match_all": {}
        }
    }


def create_pagination_latest_entries(page: int, size: int, sort_by_time_field_name: str = None):
    """
    Create the pagination query for Elasticsearch.
    This query will sort the results by the 'sort_by_time_field_name' field in descending order.
    This query will return the latest entries.

    :param page: int, the page number.
    :param size: int, the number of results per page.
    :param sort_by_time_field_name: str, the name of the field to sort by.
    :return: dict, the pagination query.
    """

    if sort_by_time_field_name is None:
        sort_by_time_field_name = "timestamp"

    # Get the pagination query.
    query = create_pagination(page=page, size=size)

    sorting: dict = {
        "sort": [
            {sort_by_time_field_name: {"order": "desc"}}  # Sort by the 'timestamp' field in descending order.
        ]
    }

    return query.update(sorting)


def add_maximum_size(query: dict):
    """
    Add the maximum size to the query.
    The maximum size is 10000 for regular queries.
    If you need more than 10000 results, you need to use the 'scroll' API or Search After.

    :param query: dict, the query to add the maximum size to.
    :return: dict, the query with the maximum size.
    """

    query['size'] = 10000

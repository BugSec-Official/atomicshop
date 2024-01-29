def match_all():
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


def match(field_name: str, search_term: str):
    """
    Create a match query for Elasticsearch.
    This query will match the documents that have the field 'field_name' set to 'search_term'.

    :param field_name: str, the name of the field to search in.
    :param search_term: str, the search term.
    :return: dict, the match query.
    """

    return {
        "query": {
            "match": {
                field_name: search_term
            }
        }
    }


def boolean_filter(field_name: str, value: bool):
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


def wildcard(field_name: str, search_term: str, exact_term: bool = False):
    """
    Create a wildcard query for Elasticsearch.
    This query uses the regular 'field_name' and not the '.keyword' version.
    What this means:
    By default, all the text fields will be processed by the standard analyzer.
    https://www.elastic.co/guide/en/elasticsearch/reference/current/analyzer.html
    https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-standard-analyzer.html
    This means that the text will be lower-cased, and the special characters will be stripped.

    Example: "TEst1-TeSt2" will be processed to ["test1", "test2"].

    To skip using the standard analyzer, we can use the '.keyword' version of the field or set the 'exact_term' to True.

    :param field_name: str, the name of the field to search in.
    :param search_term: str, the search term with the wildcard '*'.
    :param exact_term: bool, if True, the '.keyword' version of the field will be used.
    :return: dict, the wildcard query.
    """

    if exact_term:
        field_name = f"{field_name}.keyword"

    return {
        "query": {
            "wildcard": {
                field_name: {
                    "value": search_term
                }
            }
        }
    }

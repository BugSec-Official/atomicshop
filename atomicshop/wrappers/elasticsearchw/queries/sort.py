def ascending(field_name: str):
    """
    Create a sorting query for Elasticsearch.
    This query will sort the results by the 'field_name' field in ascending order.

    :param field_name: str, the name of the field to sort by.
    :return: dict, the sorting query.
    """

    return {
        "sort": [
            {field_name: {"order": "asc"}}
        ]
    }


def descending(field_name: str):
    """
    Create a sorting query for Elasticsearch.
    This query will sort the results by the 'field_name' field in descending order.

    :param field_name: str, the name of the field to sort by.
    :return: dict, the sorting query.
    """

    return {
        "sort": [
            {field_name: {"order": "desc"}}
        ]
    }


def latest_time(time_field_name: str = None):
    """
    Create a sorting query for Elasticsearch.
    This query will sort the results by the 'time_field_name' field in descending order.

    :param time_field_name: str, the name of the field to sort by.
        If None, the 'timestamp' field name will be used.
    :return: dict, the sorting query.
    """

    if time_field_name is None:
        time_field_name = "timestamp"

    return descending(field_name=time_field_name)

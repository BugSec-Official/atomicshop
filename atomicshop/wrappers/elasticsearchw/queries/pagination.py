def pagination(page: int, size: int) -> dict:
    """
    Create the pagination query for Elasticsearch.

    :param page: int, the page number.
    :param size: int, the number of results per page.
    :return: dict, the pagination query.
    """

    # Calculate the "from" parameter for Elasticsearch
    start_from = (page - 1) * size
    # Add the pagination to the query.
    pagination_dict: dict = {
        "from": start_from,
        "size": size
    }

    return pagination_dict

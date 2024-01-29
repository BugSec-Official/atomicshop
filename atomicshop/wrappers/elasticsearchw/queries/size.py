def maximum():
    """
    Add the maximum size to the query.
    The maximum size is 10000 for regular queries.
    If you need more than 10000 results, you need to use the 'scroll' API or Search After.

    :return: dict, the query with the maximum size.
    """

    return {
        "size": 10000
    }

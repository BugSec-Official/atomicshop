def match(search_terms: dict) -> dict:
    """
    Generates an Elasticsearch query based on the provided search terms.

    :param search_terms: A dictionary of field names and their corresponding search values.
    :return: A dictionary representing the Elasticsearch query.

    Usage:
    search_terms = {
        "field_name1": "search_term1",
        "field_name2": "search_term2"
    }
    """

    must_clauses = [{"match": {field: value}} for field, value in search_terms.items()]

    query = {
        "query": {
            "bool": {
                "must": must_clauses
            }
        }
    }

    return query

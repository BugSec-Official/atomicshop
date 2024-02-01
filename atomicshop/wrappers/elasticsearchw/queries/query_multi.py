def match_and_booleans(search_terms: dict) -> dict:
    """
    Generates an Elasticsearch query based on the provided search terms.

    :param search_terms: A dictionary of field names and their corresponding search values.
    :return: A dictionary representing the Elasticsearch query.

    Usage for strings:
    search_terms = {
        "field_name1": "search_term1",
        "field_name2": "search_term2"
    }

    Usage for strings and booleans:
    search_terms = {
        "field_name1": "search_term1",
        "field_name2": True
    }
    """

    must_clauses = []
    for field, value in search_terms.items():
        if isinstance(value, bool):
            # Use term query for boolean values
            must_clauses.append({"term": {field: value}})
        else:
            # Use match query for text and other types
            must_clauses.append({"match": {field: value}})

    # must_clauses = [{"term": {field: value}} for field, value in search_terms.items()]

    query = {
        "query": {
            "bool": {
                "must": must_clauses
            }
        }
    }

    return query

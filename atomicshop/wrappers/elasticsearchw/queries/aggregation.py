def get_unique_values(field_name: str, aggregation_name: str, size: int = 10):
    """
    Create an aggregation query for Elasticsearch to get the unique values of a field.
    This query will return the unique values of the field 'field_name'.

    :param field_name: str, the name of the field to get the unique values of.
    :param aggregation_name: str, the name of the aggregation.
        If you want to get the aggregation hits, you will do it by this aggregation name.



        Example:
        aggregation_name = 'unique_vendors'

        body = {
            "size": 0,  # We don't need the actual documents, just the aggregation
            "aggs": {
                aggregation_name: {
                    "terms": {
                        "field": f"{field_name}.keyword",
                        "size": size
                    }
                }
            }
        }

        res = es.search(index=index_name, body=body)
        unique_vendors = [bucket['key'] for bucket in res['aggregations'][aggregation_name]['buckets']]
    :param size: int, the maximum number of unique values to return.
    :return: dict, the aggregation query.
    """

    return {
        "size": 0,  # We don't need the actual documents, just the aggregation
        "aggs": {
            aggregation_name: {
                "terms": {
                    # When doing the aggregation on a text field, we need to use the '.keyword' version of the field.
                    "field": f"{field_name}.keyword",
                    # The default terms aggregation size is 10 in elastic. If you need more, specify it.
                    "size": size
                }
            }
        }
    }

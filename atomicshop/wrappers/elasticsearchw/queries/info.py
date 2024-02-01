"""
Query types:

Term Query
Usage: The term query is used for exact matches. It looks for the exact term in the inverted index and doesn’t analyze the query string. This is useful for searching on fields that are exact values (like IDs, tags, etc.).
Example: If your field value is "Quick Brown Fox" and you search with a term query for "quick" or "Quick", it will not match because it looks for the exact term in the field.

Match Query
Usage: The match query is more flexible. It analyzes the query string before executing the search. This means it will consider things like tokenization and stemming. It’s suitable for full-text search.
Example: Using the match query for "quick" or "Quick" on the field with "Quick Brown Fox" will likely return a match because it analyzes and tokenizes the string.

Match Phrase Query
Usage: The match_phrase query is like the match query but it also takes the order of the words into account. It is used when you want to find exact phrases or words in a specific order.
Example: If you search for "Quick Brown" with a match_phrase query on a field with the value "The Quick Brown Fox", it will match. However, searching for "Brown Quick" won't match.

Additional Query Types
Bool Query: This allows you to combine multiple queries using boolean logic (like must, should, must_not).
Range Query: Useful for finding numbers or dates in a given range.
Wildcard Query: For searches with wildcards, useful when the exact value is partially known.
Prefix Query: Finds documents containing terms that start with the specified prefix.
Fuzzy Query: Useful for dealing with typos and spelling variations.
"""


"""
AND OR:
"must" is AND
"should" is OR
"must_not" is NOT

Example with AND and OR:
You want to find all files with file_path = "/home/test1/test2/final_archive.zip" and
file_path = "test4.zip" or file_path = "_test4.zip"
Meaning you want to find all files with file_path = "/home/test1/test2/final_archive.zip/test4.zip" or
file_path = "/home/test1/test2/final_archive.zip/_test4.zip"
Since your file can be both "test4.zip" and "_test4.zip" at the same time, you need to use AND and OR.

query = {
    "query": {
        "bool": {
            "must": [
                {"match_phrase": {"file_path": "/home/test1/test2/final_archive.zip"}},
                {
                    "bool": {
                        "should": [
                            {"match_phrase": {"file_path": "test4.zip"}},
                            {"match_phrase": {"file_path": "_test4.zip"}}
                        ]
                    }
                }
            ]
        }
    }
}

This is similar to Kibana KQL:
file_path : "/home/test1/test2/final_archive.zip" and (file_path : "test4.zip") or (file_path : "_test4.zip")
"""
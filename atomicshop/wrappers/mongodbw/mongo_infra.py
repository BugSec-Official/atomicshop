from pymongo import MongoClient
import pymongo.errors


MONGODB_DEFAULT_URI: str = 'mongodb://localhost:27017/'


class MongoDBNoConnectionError(Exception):
    pass


def test_connection(
        uri: str = MONGODB_DEFAULT_URI,
        raise_exception: bool = False
) -> bool:
    """
    Test the connection to the MongoDB server.

    :param uri: str, URI to the MongoDB server.
    :param raise_exception: bool, True to raise an exception if the connection fails, False otherwise (just return
    False).
    :return: bool, True if the connection is successful, False otherwise.
    """
    try:
        client = MongoClient(uri)
        client.admin.command('ping')
        return True
    except pymongo.errors.ServerSelectionTimeoutError:
        if raise_exception:
            raise MongoDBNoConnectionError(f"Could not connect to the MongoDB server on: ")
        return False

import pymongo

from . import infrastructure


"""
DISCLAIMER: you should use the pymongo library directly instead of using the atomicshop/wrappers/mongodbw/mongodbw.py.
These are good examples to get you started, but can't really cover all the use cases you might have.
"""


def connect(uri: str = infrastructure.MONGODB_DEFAULT_URI):
    """
    Connect to a MongoDB database.
    :param uri: str, the URI of the MongoDB database.
    :return: pymongo.MongoClient, the client object.
    """
    return pymongo.MongoClient(uri)


def add_list_of_dicts_to_mongo(
        list_of_dicts: list,
        database_name: str,
        collection_name: str,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
):
    """
    Add a list of dictionaries to a MongoDB collection.
    :param list_of_dicts: list of dictionaries, the list of dictionaries to add to the collection.
    :param database_name: str, the name of the database.
    :param collection_name: str, the name of the collection.
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: None
    """

    if not mongo_client:
        mongo_client = connect()

    db = mongo_client[database_name]
    collection = db[collection_name]

    collection.insert_many(list_of_dicts)

    if close_client:
        mongo_client.close()


def remove_list_of_dicts(
        list_of_dicts: list,
        database_name: str,
        collection_name: str,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
):
    """
    Remove a list of dictionaries from a MongoDB collection.
    :param list_of_dicts: list of dictionaries, the list of dictionaries to remove from the collection.
    :param database_name: str, the name of the database.
    :param collection_name: str, the name of the collection.
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: None
    """

    if not mongo_client:
        mongo_client = connect()

    db = mongo_client[database_name]
    collection = db[collection_name]

    for doc in list_of_dicts:
        collection.delete_one(doc)

    if close_client:
        mongo_client.close()


def overwrite_list_of_dicts(
        list_of_dicts: list,
        database_name: str,
        collection_name: str,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
):
    """
    Overwrite a list of dictionaries in a MongoDB collection.
    :param list_of_dicts: list of dictionaries, the list of dictionaries to overwrite in the collection.
    :param database_name: str, the name of the database.
    :param collection_name: str, the name of the collection.
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: None
    """

    if not mongo_client:
        mongo_client = connect()

    db = mongo_client[database_name]
    collection = db[collection_name]

    collection.delete_many({})
    collection.insert_many(list_of_dicts)

    if close_client:
        mongo_client.close()


def get_all_entries_from_collection(
        database_name: str,
        collection_name: str,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
):
    """
    Get all entries from a MongoDB collection.
    :param database_name: str, the name of the database.
    :param collection_name: str, the name of the collection.
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: list of dictionaries, the list of entries from the collection.
    """

    if not mongo_client:
        mongo_client = connect()

    db = mongo_client[database_name]
    collection = db[collection_name]

    entries = list(collection.find())

    if close_client:
        mongo_client.close()

    return entries

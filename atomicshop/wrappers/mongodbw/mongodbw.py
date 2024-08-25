from typing import Union
import datetime

import pymongo

from ...basics import dicts

from . import mongo_infra


"""
DISCLAIMER: you should use the pymongo library directly instead of using the atomicshop/wrappers/mongodbw/mongodbw.py.
These are good examples to get you started, but can't really cover all the use cases you might have.
"""


def connect(uri: str = mongo_infra.MONGODB_DEFAULT_URI):
    """
    Connect to a MongoDB database.
    :param uri: str, the URI of the MongoDB database.
    :return: pymongo.MongoClient, the client object.
    """
    return pymongo.MongoClient(uri)


def index(
        object_instance: Union[list[dict], dict],
        database_name: str,
        collection_name: str,
        add_timestamp: bool = False,
        convert_mixed_lists_to_strings: bool = False,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
):
    """
    Add a dictionary or list dictionaries to a MongoDB collection.
    :param object_instance: list of dictionaries or dictionary to add to the collection.
    :param database_name: str, the name of the database.
    :param collection_name: str, the name of the collection.
    :param add_timestamp: bool, if True, a current time timestamp will be added to the object.
    :param convert_mixed_lists_to_strings: bool, if True, mixed lists or tuples when entries are strings and integers,
        the integers will be converted to strings.
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: None
    """

    _is_object_list_of_dicts_or_dict(object_instance)

    if not mongo_client:
        mongo_client = connect()
        close_client = True

    db = mongo_client[database_name]
    collection = db[collection_name]

    if convert_mixed_lists_to_strings:
        object_instance = dicts.convert_int_to_str_in_mixed_lists(object_instance)

    if add_timestamp:
        timestamp = datetime.datetime.now()
        if isinstance(object_instance, dict):
            object_instance['timestamp'] = timestamp
        elif isinstance(object_instance, list):
            for doc in object_instance:
                doc['timestamp'] = timestamp

    if isinstance(object_instance, dict):
        collection.insert_one(object_instance)
    elif isinstance(object_instance, list):
        collection.insert_many(object_instance)

    if close_client:
        mongo_client.close()


def delete(
        object_instance: Union[list[dict], dict],
        database_name: str,
        collection_name: str,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
):
    """
    Remove a list of dictionaries or a dictionary from a MongoDB collection.

    :param object_instance: list of dictionaries, the list of dictionaries to remove from the collection.
    :param database_name: str, the name of the database.
    :param collection_name: str, the name of the collection.
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: None
    """

    _is_object_list_of_dicts_or_dict(object_instance)

    if not mongo_client:
        mongo_client = connect()
        close_client = True

    db = mongo_client[database_name]
    collection = db[collection_name]

    if isinstance(object_instance, dict):
        collection.delete_one(object_instance)
    elif isinstance(object_instance, list):
        for doc in object_instance:
            collection.delete_one(doc)

    if close_client:
        mongo_client.close()


def find(
        database_name: str,
        collection_name: str,
        query: dict = None,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
):
    """
    Find entries in a MongoDB collection by query.
    :param database_name: str, the name of the database.
    :param collection_name: str, the name of the collection.
    :param query: dict, the query to search for.
        Example, search for all entries with column name 'name' equal to 'John':
            query = {'name': 'John'}
        Example, return all entries from collection:
            query = None
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: list of dictionaries, the list of entries that match the query.
    """

    if not mongo_client:
        mongo_client = connect()
        close_client = True

    db = mongo_client[database_name]
    collection = db[collection_name]

    if query is None:
        entries: list = list(collection.find())
    else:
        entries: list = list(collection.find(query))

    if close_client:
        mongo_client.close()

    return entries


def delete_all_entries_from_collection(
        database_name: str,
        collection_name: str,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
):
    """
    Remove all entries from a MongoDB collection.
    :param database_name: str, the name of the database.
    :param collection_name: str, the name of the collection.
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: None
    """

    if not mongo_client:
        mongo_client = connect()
        close_client = True

    db = mongo_client[database_name]
    collection = db[collection_name]

    collection.delete_many({})

    if close_client:
        mongo_client.close()


def overwrite_collection(
        object_instance: list,
        database_name: str,
        collection_name: str,
        add_timestamp: bool = False,
        convert_mixed_lists_to_strings: bool = False,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
):
    """
    Overwrite a MongoDB collection with list of dicts or a dict.
    :param object_instance: list of dictionaries, the list of dictionaries to overwrite in the collection.
    :param database_name: str, the name of the database.
    :param collection_name: str, the name of the collection.
    :param add_timestamp: bool, if True, a current time timestamp will be added to the object.
    :param convert_mixed_lists_to_strings: bool, if True, mixed lists or tuples when entries are strings and integers,
        the integers will be converted to strings.
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: None
    """

    _is_object_list_of_dicts_or_dict(object_instance)

    if not mongo_client:
        mongo_client = connect()
        close_client = True

    delete_all_entries_from_collection(
        database_name=database_name, collection_name=collection_name,
        mongo_client=mongo_client
    )

    index(
        object_instance=object_instance,
        database_name=database_name, collection_name=collection_name,
        add_timestamp=add_timestamp, convert_mixed_lists_to_strings=convert_mixed_lists_to_strings,
        mongo_client=mongo_client, close_client=close_client)


def _is_object_list_of_dicts_or_dict(
        object_instance: Union[list[dict], dict]
):
    if isinstance(object_instance, dict):
        return True
    elif isinstance(object_instance, list):
        if object_instance and isinstance(object_instance[0], dict):
            return True
        else:
            raise ValueError("List must contain dictionaries.")
    else:
        raise ValueError("Object must be a dictionary or a list of dictionaries.")


def get_stats_db(
        database_name: str,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
):
    """
    Get the stats of a MongoDB database.

    :param database_name: str, the name of the database.
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: dict, the stats of the collection.
    """

    if not mongo_client:
        mongo_client = connect()
        close_client = True

    db = mongo_client[database_name]

    stats = db.command("dbStats")

    if close_client:
        mongo_client.close()

    return stats


def get_stats_db_size(
        database_name: str,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
):
    """
    Get the size of a MongoDB database in bytes.

    :param database_name: str, the name of the database.
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: int, the size of the database in bytes.
    """

    stats = get_stats_db(
        database_name=database_name, mongo_client=mongo_client, close_client=close_client)

    return stats['dataSize']

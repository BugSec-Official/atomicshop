from typing import Union, Literal
import datetime
import json

# noinspection PyPackageRequirements
import pymongo
# noinspection PyPackageRequirements
import pymongo.database

from ...basics import dicts

from . import mongo_infra


"""
DISCLAIMER: you should use the pymongo library directly instead of using the atomicshop/wrappers/mongodbw/mongodbw.py.
These are good examples to get you started, but can't really cover all the use cases you might have.
"""


class MongoDBReplaceOneError(Exception):
    pass


class MongoDBUpdateOneError(Exception):
    pass


class MongoDBUpdateManyError(Exception):
    pass


class MongoDBWrapper:
    def __init__(
            self,
            db_name: str,
            uri: str = mongo_infra.MONGODB_DEFAULT_URI
    ):
        self.db_name: str = db_name
        self.uri: str = uri

        # noinspection PyTypeChecker
        self.client: pymongo.MongoClient = None
        # noinspection PyTypeChecker
        self.db: pymongo.database.Database = None

    def connect(self):
        """
        Connect to a MongoDB database.
        :return: pymongo.MongoClient, the client object.
        """

        if not self.client:
            self.client = connect(uri=self.uri)
            self.db = get_db(database=self.db_name, mongo_client=self.client)

    def disconnect(self):
        """
        Disconnect from a MongoDB database.
        :return: None
        """

        if self.client:
            self.client.close()
            self.client = None

    def insert(
            self,
            object_instance: Union[list[dict], dict],
            collection_name: str,
            add_timestamp: bool = False,
            convert_mixed_lists_to_strings: bool = False
    ):
        """
        Add a dictionary or list dictionaries to a MongoDB collection.
        :param object_instance: list of dictionaries or dictionary to add to the collection.
        :param collection_name: str, the name of the collection.
        :param add_timestamp: bool, if True, a current time timestamp will be added to the object.
        :param convert_mixed_lists_to_strings: bool, if True, mixed lists or tuples when entries are
            strings and integers, the integers will be converted to strings.

        :return: None
        """

        self.connect()

        insert(
            object_instance=object_instance,
            database=self.db, collection_name=collection_name,
            add_timestamp=add_timestamp, convert_mixed_lists_to_strings=convert_mixed_lists_to_strings,
            mongo_client=self.client, close_client=False)

    def delete(
            self,
            filter_instance: Union[list[dict], dict],
            collection_name: str
    ):
        """
        Remove a dict or list of dictionaries or a dictionary from a MongoDB collection.
        For pure mongo, this is the list of queries to remove.
        Each query for a single item.

        :param filter_instance: dict or list of dictionaries (the list of filters to remove from the collection).
        :param collection_name: str, the name of the collection.

        :return: None
        """

        self.connect()

        delete(
            filter_instance=filter_instance,
            database=self.db, collection_name=collection_name,
            mongo_client=self.client, close_client=False)

    def delete_many(
            self,
            filter_query: dict,
            collection_name: str
    ):
        """
        Remove all entries that match the filter query from a MongoDB collection.

        :param filter_query: dict, the filter query to search for.
            Example, search for all entries with column name 'name' equal to 'John':
                filter query = {'name': 'John'}
        :param collection_name: str, the name of the collection.

        :return: result of the operation.
        """

        self.connect()

        return delete_many(
            filter_query=filter_query,
            database=self.db, collection_name=collection_name,
            mongo_client=self.client, close_client=False)

    def create_index(
            self,
            collection_name: str,
            fields_list: list[tuple[str, int]],
            name: str = None
    ):
        """
        Create an index in a MongoDB collection.
        :param collection_name: str, the name of the collection.
        :param fields_list: list of tuples, each tuple will contain
            [0] string of the field name and
            [1] the integer value of the order
                to sort by, this is pymongo default, 1 for ascending and -1 for descending.
            Example:
                [
                    ('vendor', 1),
                    ('model', -1)
                ]

            Explanation:
                This will create a compound index that will sort the collection by the field 'vendor'
                in ascending order, and then by the field 'model' in descending order.
        :param name: str, the name of the index.

        :return: None
        """

        self.connect()

        create_index(
            database=self.db, collection_name=collection_name,
            fields_list=fields_list, name=name,
            mongo_client=self.client, close_client=False)

    def find(
            self,
            collection_name: str,
            filter_query: dict = None,
            projection: dict = None,
            page: int = None,
            items: int = None,
            sort: dict[str, Literal[
                'asc', 'desc',
                1, -1]] = None,
            convert_object_id_to_str: bool = False,
            keys_convert_to_dict: list[str] = None
    ) -> list[dict]:
        """
        Find entries in a MongoDB collection by query.
        :param collection_name: str, the name of the collection.
        :param filter_query: dict, the query to search for.
            Example, search for all entries with column name 'name' equal to 'John':
                filter_query = {'name': 'John'}
            Example, return all entries from collection:
                filter_query = None

            CHECK MORE EXAMPLES IN THE DOCSTRING OF THE FUNCTION 'find' BELOW which is not in this class.
        :param projection: dict, the only fields to return or exclude.
        :param page: int, the page number (Optional).
            The results are filtered after results are fetched from db.
        :param items: int, the number of results per page (Optional).
            The results are filtered after results are fetched from db.
        :param sort: dict, the name of the field and the order to sort the containers by.
            You can use several fields to sort the containers by several fields.
            In this case the containers will be sorted by the first field, then by the second field, etc.
            You can also use only singular field to sort the containers by only one field.
            Usage:
                {
                    field_name: order
                }
            Example:
                {
                    'vendor': 'asc',
                    'model': 'desc'
                }

            Or example using integers:
                {
                    'vendor': 1,
                    'model': -1
                }

        :param convert_object_id_to_str: bool, if True, the '_id' field will be converted to a string.
            The '_id' field is an ObjectId type, which is a complex object, it can be converted to a string for simpler
            processing.
        :param keys_convert_to_dict: list, the keys of the documents that should be converted from string to dict.
            Recursively searches for keys in specified list in a nested dictionary in result entries list,
            and converts their values using 'json.loads' if found.
        :return: list of dictionaries, the list of entries that match the query.
        """

        self.connect()

        entries: list[dict] = find(
            database=self.db, collection_name=collection_name,
            filter_query=filter_query, projection=projection,
            page=page, items=items, sort=sort,
            convert_object_id_to_str=convert_object_id_to_str, key_convert_to_dict=keys_convert_to_dict,
            mongo_client=self.client, close_client=False)

        return entries

    def distinct(
            self,
            collection_name: str,
            field_name: str,
            filter_query: dict = None
    ) -> list:
        """
        Get distinct values of a field from a MongoDB collection.
        Example:
            Example database:
                {
                    'users': [
                        {'name': 'John', 'age': 25},
                        {'name': 'John', 'age': 30},
                        {'name': 'Alice', 'age': 25}
                    ]
                }

            Get distinct values of the field 'name' from the collection 'users':
                distinct('users', 'name')

            Output:
                ['John', 'Alice']

        :param collection_name: str, the name of the collection.
        :param field_name: str, the name of the field.
        :param filter_query: dict, the filter query to search for. If None, the filter query will not be executed.

        :return: list, the list of distinct values.
        """

        self.connect()

        distinct_values = distinct(
            database=self.db, collection_name=collection_name,
            field_name=field_name, filter_query=filter_query, mongo_client=self.client, close_client=False)

        return distinct_values

    def update(
            self,
            collection_name: str,
            filter_query: dict,
            update_instance: Union[dict, list[dict]],
            add_timestamp: bool = False,
            convert_mixed_lists_to_strings: bool = False
    ):
        """
        Update one entry in a MongoDB collection by filter query.
        :param collection_name: str, the name of the collection.
        :param filter_query: dict, the filter query to search for.
            Example, search for all entries with column name 'name' equal to 'John':
                filter_query = {'name': 'John'}
            Find by Object id:
                filter_query = {'_id': ObjectId('5f3e3b3b4b9f3b3b4b9f3b3b')}
        :param update_instance: dict or list of dicts, the update to apply.
            Get examples for operators for each dict in the docstring of the function 'update' below.
        :param add_timestamp: bool, if True, a current time timestamp will be added to the object.
        :param convert_mixed_lists_to_strings: bool, if True, mixed lists or tuples when entries are
            strings and integers, the integers will be converted to strings.
        :return: result of the operation.
        """

        self.connect()

        return update(
            database=self.db, collection_name=collection_name,
            filter_query=filter_query, update_instance=update_instance, add_timestamp=add_timestamp,
            convert_mixed_lists_to_strings=convert_mixed_lists_to_strings,
            mongo_client=self.client, close_client=False)

    def replace(
            self,
            collection_name: str,
            filter_query: dict,
            replacement: dict,
            add_timestamp: bool = False,
            convert_mixed_lists_to_strings: bool = False
    ):
        """
        Replace one entry in a MongoDB collection by filter query.
        :param collection_name: str, the name of the collection.
        :param filter_query: dict, the filter query to search for.
            Example, search for all entries with column name 'name' equal to 'John':
                filter_query = {'name': 'John'}
            Find by Object id:
                filter_query = {'_id': ObjectId('5f3e3b3b4b9f3b3b4b9f3b3b')}
        :param replacement: dict, the replacement to apply.
        :param add_timestamp: bool, if True, a current time timestamp will be added to the object.
        :param convert_mixed_lists_to_strings: bool, if True, mixed lists or tuples when entries are

        :return: result of the operation.
        """

        self.connect()

        return replace(
            database=self.db, collection_name=collection_name,
            filter_query=filter_query, replacement=replacement,
            add_timestamp=add_timestamp, convert_mixed_lists_to_strings=convert_mixed_lists_to_strings,
            mongo_client=self.client, close_client=False)

    def get_all_indexes_in_collection(
            self,
            collection_name: str
    ) -> dict:
        """
        Get all indexes in a MongoDB collection.
        :param collection_name: str, the name of the collection.
        :return: list of dictionaries, the list of indexes.
        """

        self.connect()

        indexes: dict = get_all_indexes_in_collection(
            database=self.db, collection_name=collection_name,
            mongo_client=self.client, close_client=False)

        return indexes

    def is_index_name_in_collection(
            self,
            collection_name: str,
            index_name: str
    ) -> bool:
        """
        Check if an index name exists in a MongoDB collection.
        :param collection_name: str, the name of the collection.
        :param index_name: str, the name of the index.
        :return: bool, if the index name exists in the collection.
        """

        self.connect()

        exists: bool = is_index_name_in_collection(
            database=self.db, collection_name=collection_name,
            index_name=index_name, mongo_client=self.client, close_client=False)

        return exists

    def count_entries_in_collection(
            self,
            collection_name: str,
            filter_query: dict = None
    ) -> int:
        """
        Count entries in a MongoDB collection by query.

        :param collection_name: str, the name of the collection.
        :param filter_query: dict, the query to search for.
            Example, search for all entries with column name 'name' equal to 'John':
                filter_query = {'name': 'John'}
            Example, return all entries from collection:
                filter_query = None

        :return: int, the number of entries that match the query.
        """

        self.connect()

        count = count_entries_in_collection(
            database=self.db, collection_name=collection_name,
            filter_query=filter_query, mongo_client=self.client, close_client=False)

        return count

    def get_client(self):
        return self.client

    def get_stats_db(
            self
    ):
        """
        Get the stats of a MongoDB database.

        :return: dict, the stats of the collection.
        """

        self.connect()

        stats = get_stats_db(
            database=self.db, mongo_client=self.client, close_client=False)

        return stats

    def get_stats_db_size(
            self
    ):
        """
        Get the size of a MongoDB database in bytes.

        :return: int, the size of the database in bytes.
        """

        self.connect()

        size = get_stats_db_size(
            database=self.db, mongo_client=self.client, close_client=False)

        return size


def connect(uri: str = mongo_infra.MONGODB_DEFAULT_URI):
    """
    Connect to a MongoDB database.
    :param uri: str, the URI of the MongoDB database.
    :return: pymongo.MongoClient, the client object.
    """
    return pymongo.MongoClient(uri)


def get_db(
        database: str,
        mongo_client: pymongo.MongoClient = None
) -> pymongo.database.Database:
    """
    Get a MongoDB database object.
    :param database: String, the name of the database.
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :return: pymongo.database.Database, the database object.
    """

    if not mongo_client:
        mongo_client = connect()

    return mongo_client[database]


def insert(
        object_instance: Union[list[dict], dict],
        database: Union[str, pymongo.database.Database],
        collection_name: str,
        add_timestamp: bool = False,
        convert_mixed_lists_to_strings: bool = False,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
):
    """
    Add a dictionary or list dictionaries to a MongoDB collection.
    :param object_instance: list of dictionaries or dictionary to add to the collection.
    :param database: String or the database object.
        str - the name of the database. In this case the database object will be created.
        pymongo.database.Database - the database object that will be used instead of creating a new one.
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

    db = _get_pymongo_db_from_string_or_pymongo_db(database, mongo_client)
    collection = db[collection_name]

    if convert_mixed_lists_to_strings:
        if isinstance(object_instance, dict):
            object_instance = dicts.convert_int_to_str_in_mixed_lists(object_instance)
        elif isinstance(object_instance, list):
            for doc_index, doc in enumerate(object_instance):
                object_instance[doc_index] = dicts.convert_int_to_str_in_mixed_lists(doc)

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
        filter_instance: Union[list[dict], dict],
        database: Union[str, pymongo.database.Database],
        collection_name: str,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
):
    """
    Remove a dict or list of dictionaries or a dictionary from a MongoDB collection.

    :param filter_instance: dict or list of dictionaries,
        dict, the regular filter for pymongo.
        list of dictionaries to remove from the collection, for pure mongo, this is the list of filtered to remove.
            Each filter for a single item.
    :param database: String or the database object.
        str - the name of the database. In this case the database object will be created.
        pymongo.database.Database - the database object that will be used instead of creating a new one.
    :param collection_name: str, the name of the collection.
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: None
    """

    _is_object_list_of_dicts_or_dict(filter_instance)

    if not mongo_client:
        mongo_client = connect()
        close_client = True

    db = _get_pymongo_db_from_string_or_pymongo_db(database, mongo_client)
    collection = db[collection_name]

    if isinstance(filter_instance, dict):
        collection.delete_one(filter_instance)
    elif isinstance(filter_instance, list):
        for doc in filter_instance:
            collection.delete_one(doc)

    if close_client:
        mongo_client.close()


def delete_many(
        filter_query: dict,
        database: Union[str, pymongo.database.Database],
        collection_name: str,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
):
    """
    Remove all entries that match the filter query from a MongoDB collection.

    :param filter_query: dict, the filter query to search for.
        Example, search for all entries with column name 'name' equal to 'John':
            filter_query = {'name': 'John'}
    :param database: String or the database object.
        str - the name of the database. In this case the database object will be created.
        pymongo.database.Database - the database object that will be used instead of creating a new one.
    :param collection_name: str, the name of the collection.
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: result of the operation.
    """

    if not mongo_client:
        mongo_client = connect()
        close_client = True

    db = _get_pymongo_db_from_string_or_pymongo_db(database, mongo_client)
    collection = db[collection_name]

    result = collection.delete_many(filter_query)

    if close_client:
        mongo_client.close()

    return result


def create_index(
        database: Union[str, pymongo.database.Database],
        collection_name: str,
        fields_list: list[tuple[str, int]],
        name: str = None,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
):
    """
    Create an index in a MongoDB collection.
    :param database: String or the database object.
        str - the name of the database. In this case the database object will be created.
        pymongo.database.Database - the database object that will be used instead of creating a new one.
    :param collection_name: str, the name of the collection.
    :param fields_list: list of tuples, each tuple will contain
        [0] string of the field name and
        [1] the integer value of the order
            to sort by, this is pymongo default, 1 for ascending and -1 for descending.
        Example:
            [
                ('vendor', 1),
                ('model', -1)
            ]

        Explanation:
            This will create a compound index that will sort the collection by the field 'vendor' in ascending order,
            and then by the field 'model' in descending order.
    :param name: str, the name of the index.
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: None
    """

    if not mongo_client:
        mongo_client = connect()
        close_client = True

    db = _get_pymongo_db_from_string_or_pymongo_db(database, mongo_client)
    collection = db[collection_name]

    collection.create_index(fields_list, name=name)

    if close_client:
        mongo_client.close()


def find(
        database: Union[str, pymongo.database.Database],
        collection_name: str,
        filter_query: dict = None,
        projection: dict = None,
        page: int = None,
        items: int = None,
        sort: Union[
            dict[str, Literal[
                'asc', 'desc',
                'ASC', 'DESC',
                1, -1]],
            list[tuple[
                str, Literal[1, -1]]],
            None] = None,
        convert_object_id_to_str: bool = False,
        key_convert_to_dict: list[str] = None,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
) -> list[dict]:
    """
    Find entries in a MongoDB collection by query.
    :param database: String or the database object.
        str - the name of the database. In this case the database object will be created.
        pymongo.database.Database - the database object that will be used instead of creating a new one.
    :param collection_name: str, the name of the collection.
    :param filter_query: dict, the query to search for.
        Example, return all entries from collection:
            filter_query = None
        Example, search for all entries with column name 'name' equal to 'John':
            filter_query = {'name': 'John'}

        Additional parameters to use in the value of the query:
        $regex: Will search for a regex pattern in the field.
            Example for searching for a value that contains 'test':
            filter_query = {'field_name': {'$regex': 'test'}}
            This will return all entries where the field 'field_name' contains the word 'test':
            'test', 'test1', '2test', etc.

            Example for searching for a value that starts with 'test':
            filter_query = {'field_name': {'$regex': '^test'}}
        $options: The options for the regex search.
            'i': case-insensitive search.
                Example for case-insensitive search:
                filter_query = {'field_name': {'$regex': 'test', '$options': 'i'}}
        $and: Will search for entries that match all the conditions.
            Example for searching for entries that match all the conditions:
            filter_query = {'$and': [
                {'field_name1': 'value1'},
                {'field_name2': 'value2'}
            ]}
        $or: Will search for entries that match at least one of the conditions.
            Example for searching for entries that match at least one of the conditions:
            filter_query = {'$or': [
                {'field_name1': 'value1'},
                {'field_name2': 'value2'}
            ]}
        $in: Will search for a value in a list of values.
            Example for searching for a value that is in a list of values:
            filter_query = {'field_name': {'$in': ['value1', 'value2', 'value3']}}
        $nin: Will search for a value not in a list of values.
            Example for searching for a value that is not in a list of values:
            filter_query = {'field_name': {'$nin': ['value1', 'value2', 'value3']}}
        $exists: Will search for entries where the field exists or not.
            Example for searching for entries where the field exists:
            filter_query = {'field_name': {'$exists': True}}
            Example for searching for entries where the field does not exist:
            filter_query = {'field_name': {'$exists': False}}
        $ne: Will search for entries where the field is not equal to the value.
            Example for searching for entries where the field is not equal to the value:
            filter_query = {'field_name': {'$ne': 'value'}}

    :param projection: dict, the only fields to return or exclude.
        Example, return only the field 'name' and 'age':
            projection = {'name': 1, 'age': 1}
        Example, return all fields except the field 'age':
            projection = {'age': 0}
        Example, return all fields except the field 'age' and 'name':
            projection = {'age': 0, 'name': 0}
    :param page: int, the page number (Optional).
    :param items: int, the number of results per page (Optional).
    :param sort: dict or list of tuples:
        dict, the name of the field and the order to sort the containers by.
            You can use several fields to sort the containers by several fields.
            In this case the containers will be sorted by the first field, then by the second field, etc.
            You can also use only singular field to sort the containers by only one field.
            Usage:
                {
                    field_name: order
                }
            Example:
                {
                    'vendor': 'asc',
                    'model': 'desc'
                }

            Or example using integers:
                {
                    'vendor': 1,
                    'model': -1
                }

        list of tuples, each tuple will contain [0] string of the field name and [1] the integer value of the order
            to sort by, this is pymongo default, 1 for ascending and -1 for descending.
    :param convert_object_id_to_str: bool, if True, the '_id' field will be converted to a string.
        The '_id' field is an ObjectId type, which is a complex object, it can be converted to a string for simpler
        processing.
    :param key_convert_to_dict: list, the keys of the documents that should be converted from string to dict.
        Recursively searches for keys in specified list in a nested dictionary in result entries list,
        and converts their values using 'json.loads' if found.
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: list of dictionaries, the list of entries that match the query.
    """

    if page and not items:
        raise ValueError("If 'page' is provided, 'items' must be provided as well.")
    elif items and not page:
        page = 1

    if sort and isinstance(sort, dict):
        for key_to_sort_by, order in sort.items():
            if order.lower() not in ['asc', 'desc', 1, -1]:
                raise ValueError("The order must be 'asc', 'desc', 1 or -1.")

    if not mongo_client:
        mongo_client = connect()
        close_client = True

    db = _get_pymongo_db_from_string_or_pymongo_db(database, mongo_client)
    collection = db[collection_name]

    if filter_query is None:
        filter_query = {}

    # 'skip_items' can be 0, if we ask for the first page, so we still need to cut the number of items.
    # In this case checking if 'items' is not None is enough.
    if items is None:
        items = 0

    # Calculate the number of documents to skip
    skip_items = 0
    if page and items:
        skip_items = (page - 1) * items

    # noinspection PyTypeChecker
    sorting_list_of_tuples: list[tuple[str, int]] = None
    if sort:
        sorting_list_of_tuples = []
        if isinstance(sort, dict):
            for key_to_sort_by, order in sort.items():
                if order.lower() == 'asc':
                    order = pymongo.ASCENDING
                elif order.lower() == 'desc':
                    order = pymongo.DESCENDING

                sorting_list_of_tuples.append((key_to_sort_by, order))
        elif sort and isinstance(sort, list):
            sorting_list_of_tuples = sort

        # collection_items = collection_items.sort(sorting_list_of_tuples)
    collection_items = collection.find(
        filter_query, projection=projection, sort=sorting_list_of_tuples, skip=skip_items, limit=items)

    # # 'skip_items' can be 0, if we ask for the first page, so we still need to cut the number of items.
    # # In this case checking if 'items' is not None is enough.
    # if items:
    #     collection_items = collection_items.skip(skip_items).limit(items)

    entries: list[dict] = list(collection_items)

    if entries and convert_object_id_to_str and '_id' in entries[0]:
        for entry_index, entry in enumerate(entries):
            entries[entry_index]['_id'] = str(entry['_id'])

    if key_convert_to_dict and entries:
        entries = _convert_key_values_to_objects(keys_convert_to_dict=key_convert_to_dict, returned_data=entries)

    if close_client:
        mongo_client.close()

    return entries


def distinct(
        database: Union[str, pymongo.database.Database],
        collection_name: str,
        field_name: str,
        filter_query: dict = None,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
) -> list:
    """
    Get distinct values of a field from a MongoDB collection.
    Example:
        Example database:
            {
                'users': [
                    {'name': 'John', 'age': 25},
                    {'name': 'John', 'age': 30},
                    {'name': 'Alice', 'age': 25}
                ]
            }

        Get distinct values of the field 'name' from the collection 'users':
            distinct('my_db', 'users', 'name')

        Output:
            ['John', 'Alice']

    :param database: String or the database object.
        str - the name of the database. In this case the database object will be created.
        pymongo.database.Database - the database object that will be used instead of creating a new one.
    :param collection_name: str, the name of the collection.
    :param field_name: str, the name of the field.
    :param filter_query: dict, the filter query to search for.
        If None, the filter query will not be executed.
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: list, the list of distinct values.
    """

    if not mongo_client:
        mongo_client = connect()
        close_client = True

    db = _get_pymongo_db_from_string_or_pymongo_db(database, mongo_client)
    collection = db[collection_name]

    distinct_values = collection.distinct(field_name, filter_query)

    if close_client:
        mongo_client.close()

    return distinct_values


def update(
        database: Union[str, pymongo.database.Database],
        collection_name: str,
        filter_query: dict,
        update_instance: Union[dict, list[dict]],
        add_timestamp: bool = False,
        convert_mixed_lists_to_strings: bool = False,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
):
    """
    Update one entry in a MongoDB collection by filter query.
    :param database: String or the database object.
        str - the name of the database. In this case the database object will be created.
        pymongo.database.Database - the database object that will be used instead of creating a new one.
    :param collection_name: str, the name of the collection.
    :param filter_query: dict, the filter query to search for.
        Example, search for all entries with column name 'name' equal to 'John':
            filter_query = {'name': 'John'}
        Find by Object id:
            filter_query = {'_id': ObjectId('5f3e3b3b4b9f3b3b4b9f3b3b')}
    :param update_instance: dict or list of dicts, the update to apply.
        If dict, the update will be applied to one entry using 'update_one'.
        If list of dicts, the update will be applied to multiple entries using 'update_many'.

        Examples for operators for each dict:
        $set: update the column 'name' to 'Alice':
            update_instance = {'$set': {'name': 'Alice'}}
        $inc: increment the column 'age' by 1:
            update_instance = {'$inc': {'age': 1}}
        $unset: remove the column 'name':
            update_instance = {'$unset': {'name': ''}}
        $push: add a value to the list 'hobbies':
            update_instance = {'$push': {'hobbies': 'swimming'}}
        $pull: remove a value from the list 'hobbies':
            update_instance = {'$pull': {'hobbies': 'swimming'}}
    :param add_timestamp: bool, if True, a current time timestamp will be added to the object.
    :param convert_mixed_lists_to_strings: bool, if True, mixed lists or tuples when entries are
        strings and integers, the integers will be converted to strings.
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: None
    """

    if not mongo_client:
        mongo_client = connect()
        close_client = True

    db = _get_pymongo_db_from_string_or_pymongo_db(database, mongo_client)
    collection = db[collection_name]

    if convert_mixed_lists_to_strings:
        if isinstance(update_instance, dict):
            update_instance = dicts.convert_int_to_str_in_mixed_lists(update_instance)
        elif isinstance(update_instance, list):
            for doc_index, doc in enumerate(update_instance):
                update_instance[doc_index] = dicts.convert_int_to_str_in_mixed_lists(doc)

    if add_timestamp:
        timestamp = datetime.datetime.now()
        if isinstance(update_instance, dict):
            update_instance['timestamp'] = timestamp
        elif isinstance(update_instance, list):
            for doc in update_instance:
                doc['timestamp'] = timestamp

    result = None
    if isinstance(update_instance, dict):
        result = collection.update_one(filter_query, update_instance)
    elif isinstance(update_instance, list):
        result = collection.update_many(filter_query, update_instance)

    if result.matched_count == 0:
        raise MongoDBUpdateOneError("No document found to update.")

    if close_client:
        mongo_client.close()

    return result


def replace(
        database: Union[str, pymongo.database.Database],
        collection_name: str,
        filter_query: dict,
        replacement: dict,
        add_timestamp: bool = False,
        convert_mixed_lists_to_strings: bool = False,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
):
    """
    Replace one entry in a MongoDB collection by filter query.
    :param database: String or the database object.
        str - the name of the database. In this case the database object will be created.
        pymongo.database.Database - the database object that will be used instead of creating a new one.
    :param collection_name: str, the name of the collection.
    :param filter_query: dict, the filter query to search for.
        Example, search for all entries with column name 'name' equal to 'John':
            filter_query = {'name': 'John'}
        Find by Object id:
            filter_query = {'_id': ObjectId('5f3e3b3b4b9f3b3b4b9f3b3b')}
    :param replacement: dict, the replacement to apply.
    :param add_timestamp: bool, if True, a current time timestamp will be added to the object.
    :param convert_mixed_lists_to_strings: bool, if True, mixed lists or tuples when entries are strings and integers,
        the integers will be converted to strings.
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: None
    """

    if not mongo_client:
        mongo_client = connect()
        close_client = True

    db = _get_pymongo_db_from_string_or_pymongo_db(database, mongo_client)
    collection = db[collection_name]

    if convert_mixed_lists_to_strings:
        replacement = dicts.convert_int_to_str_in_mixed_lists(replacement)

    if add_timestamp:
        timestamp = datetime.datetime.now()
        replacement['timestamp'] = timestamp

    result = collection.replace_one(filter_query, replacement)
    if result.matched_count == 0:
        raise MongoDBReplaceOneError("No document found to replace.")

    if close_client:
        mongo_client.close()

    return result


def get_all_indexes_in_collection(
        database: Union[str, pymongo.database.Database],
        collection_name: str,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
) -> dict:
    """
    Get all indexes in a MongoDB collection.
    :param database: String or the database object.
        str - the name of the database. In this case the database object will be created.
        pymongo.database.Database - the database object that will be used instead of creating a new one.
    :param collection_name: str, the name of the collection.
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: list, the list of indexes.
    """

    if not mongo_client:
        mongo_client = connect()
        close_client = True

    db = _get_pymongo_db_from_string_or_pymongo_db(database, mongo_client)
    collection = db[collection_name]

    # noinspection PyTypeChecker
    indexes: dict = collection.index_information()

    if close_client:
        mongo_client.close()

    return indexes


def is_index_name_in_collection(
        database: Union[str, pymongo.database.Database],
        collection_name: str,
        index_name: str,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
) -> bool:
    """
    Check if an index name is in a MongoDB collection.
    :param database: String or the database object.
        str - the name of the database. In this case the database object will be created.
        pymongo.database.Database - the database object that will be used instead of creating a new one.
    :param collection_name: str, the name of the collection.
    :param index_name: str, the name of the index.
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: bool, if the index name is in the collection.
    """

    indexes = get_all_indexes_in_collection(
        database=database, collection_name=collection_name,
        mongo_client=mongo_client, close_client=close_client)

    return index_name in indexes


def count_entries_in_collection(
        database: Union[str, pymongo.database.Database],
        collection_name: str,
        filter_query: dict = None,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
) -> int:
    """
    Count entries in a MongoDB collection by query.

    :param database: String or the database object.
        str - the name of the database. In this case the database object will be created.
        pymongo.database.Database - the database object that will be used instead of creating a new one.
    :param collection_name: str, the name of the collection.
    :param filter_query: dict, the query to search for.
        Example, search for all entries with column name 'name' equal to 'John':
            filter_query = {'name': 'John'}
        Example, return all entries from collection:
            filter_query = None
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: int, the number of entries that match the query.
    """

    if not mongo_client:
        mongo_client = connect()
        close_client = True

    db = _get_pymongo_db_from_string_or_pymongo_db(database, mongo_client)
    collection = db[collection_name]

    if filter_query is None:
        filter_query = {}

    count = collection.count_documents(filter_query)

    if close_client:
        mongo_client.close()

    return count


def delete_all_entries_from_collection(
        database: Union[str, pymongo.database.Database],
        collection_name: str,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
):
    """
    Remove all entries from a MongoDB collection.
    :param database: String or the database object.
        str - the name of the database. In this case the database object will be created.
        pymongo.database.Database - the database object that will be used instead of creating a new one.
    :param collection_name: str, the name of the collection.
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: None
    """

    if not mongo_client:
        mongo_client = connect()
        close_client = True

    db = _get_pymongo_db_from_string_or_pymongo_db(database, mongo_client)
    collection = db[collection_name]

    collection.delete_many({})

    if close_client:
        mongo_client.close()


def overwrite_collection(
        object_instance: list,
        database: Union[str, pymongo.database.Database],
        collection_name: str,
        add_timestamp: bool = False,
        convert_mixed_lists_to_strings: bool = False,
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
):
    """
    Overwrite a MongoDB collection with list of dicts or a dict.
    :param object_instance: list of dictionaries, the list of dictionaries to overwrite in the collection.
    :param database: String or the database object.
        str - the name of the database. In this case the database object will be created.
        pymongo.database.Database - the database object that will be used instead of creating a new one.
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
        database=database, collection_name=collection_name,
        mongo_client=mongo_client
    )

    insert(
        object_instance=object_instance,
        database=database, collection_name=collection_name,
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


def _get_pymongo_db_from_string_or_pymongo_db(
        database: Union[str, pymongo.database.Database],
        mongo_client: pymongo.MongoClient
) -> pymongo.database.Database:
    """
    Get a pymongo.database.Database object from a string or a pymongo.database.Database object.

    :param database: Union[str, pymongo.database.Database], the database object or the name of the database.
        If the database is a string, the database object will be created.
        If the database is a pymongo.database.Database object, it will be returned as is.
    :param mongo_client: mongodb.MongoClient, the connection object.
    :return: pymongo.database.Database, the database object.
    """

    if isinstance(database, str):
        return mongo_client[database]
    elif isinstance(database, pymongo.database.Database):
        return database
    else:
        raise ValueError("Database must be a string (database name) or a pymongo.database.Database object.")


def get_stats_db(
        database: Union[str, pymongo.database.Database],
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
):
    """
    Get the stats of a MongoDB database.

    :param database: String or the database object.
        str - the name of the database. In this case the database object will be created.
        pymongo.database.Database - the database object that will be used instead of creating a new one.
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: dict, the stats of the collection.
    """

    if not mongo_client:
        mongo_client = connect()
        close_client = True

    db = _get_pymongo_db_from_string_or_pymongo_db(database, mongo_client)

    stats = db.command("dbStats")

    if close_client:
        mongo_client.close()

    return stats


def get_stats_db_size(
        database: Union[str, pymongo.database.Database],
        mongo_client: pymongo.MongoClient = None,
        close_client: bool = False
):
    """
    Get the size of a MongoDB database in bytes.

    :param database: String or the database object.
        str - the name of the database. In this case the database object will be created.
        pymongo.database.Database - the database object that will be used instead of creating a new one.
    :param mongo_client: pymongo.MongoClient, the connection object.
        If None, a new connection will be created to default URI.
    :param close_client: bool, if True, the connection will be closed after the operation.

    :return: int, the size of the database in bytes.
    """

    stats = get_stats_db(
        database=database, mongo_client=mongo_client, close_client=close_client)

    return stats['dataSize']


def _convert_key_values_to_objects(
        keys_convert_to_dict: list[str],
        returned_data: Union[dict, list]
) -> Union[dict, list]:
    """
    Recursively searches for provided keys from the 'keys_convert_to_dict' list like 'test1' and 'test2'
    in a nested dictionary 'returned_data' and converts their values using "json.loads" if found.

    :param keys_convert_to_dict: list, the keys of the documents that should be converted from string to dict.
    :param returned_data: The nested dictionary to search through.
    :type returned_data: dict
    """

    if isinstance(returned_data, dict):
        for key, value in returned_data.items():
            if key in keys_convert_to_dict:
                # Can be that the value is None, so we don't need to convert it.
                if value is None:
                    continue

                try:
                    returned_data[key] = json.loads(value)
                except (ValueError, TypeError):
                    # This is needed only to know the possible exception types.
                    raise
            else:
                _convert_key_values_to_objects(keys_convert_to_dict, value)
    elif isinstance(returned_data, list):
        for i, item in enumerate(returned_data):
            returned_data[i] = _convert_key_values_to_objects(keys_convert_to_dict, item)

    return returned_data

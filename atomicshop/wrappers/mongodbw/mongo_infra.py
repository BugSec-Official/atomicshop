import os
from typing import Union

from pymongo import MongoClient
import pymongo.errors

from ... import filesystem

if os.name == 'nt':
    from ... import get_process_list


WHERE_TO_SEARCH_FOR_MONGODB_EXE: str = 'C:\\Program Files\\MongoDB\\Server\\'
MONGODB_EXE_NAME: str = 'mongod.exe'
MONGODB_DEFAULT_URI: str = 'mongodb://localhost:27017/'


class MongoDBNoConnectionError(Exception):
    pass


def test_connection(
        uri: str = MONGODB_DEFAULT_URI,
        raise_exception: bool = False
) -> bool:
    try:
        client = MongoClient(uri)
        client.admin.command('ping')
        return True
    except pymongo.errors.ServerSelectionTimeoutError:
        if raise_exception:
            raise MongoDBNoConnectionError(f"Could not connect to the MongoDB server on: ")
        return False


def is_service_running() -> bool:
    """
    Check if the MongoDB service is running.
    :return: bool, True if the MongoDB service is running, False otherwise.
    """

    if os.name == 'nt':
        current_processes: dict = (
            get_process_list.GetProcessList(get_method='pywin32', connect_on_init=True).get_processes())

        for pid, process_info in current_processes.items():
            if MONGODB_EXE_NAME in process_info['name']:
                return True
    else:
        raise NotImplementedError("This function is not implemented for this OS.")

    return False


def is_installed() -> Union[str, None]:
    """
    Check if MongoDB is installed.
    :return: string if MongoDB executable is found, None otherwise.
    """

    return filesystem.find_file(MONGODB_EXE_NAME, WHERE_TO_SEARCH_FOR_MONGODB_EXE)

from ...psycopgw import psycopgw


def get_file_object(config_db: dict, uid: str = None):
    """
    Get included UIDs from a firmware UID.
    :param config_db: dict, database config data.
    :param uid: string, firmware UID. If None, get all the UIDs.

    :return: list, included UIDs.
    """

    if uid is None:
        query = f"SELECT * FROM file_object"
    else:
        query = f"SELECT * FROM file_object WHERE uid = '{uid}'"

    result: list = psycopgw.get_query_data(
        query=query, dbname=config_db['database'], user=config_db['ro-user'], password=config_db['ro-pw'],
        host=config_db['server'], port=config_db['port'], leave_connected=True)

    return result

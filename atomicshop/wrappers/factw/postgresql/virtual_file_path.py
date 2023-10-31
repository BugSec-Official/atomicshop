from ...psycopgw import psycopgw


def get_virtual_path(config_db: dict, parent_uid: str = None, file_uid: str = None):
    """
    Get included UIDs from a firmware UID.
    :param config_db: dict, database config data.
    :param parent_uid: string, parent firmware UID. If None, get all the UIDs.
    :param file_uid: string, file UID that is inside firmware. If None, get all the UIDs.

    :return: list, included UIDs.
    """

    query = f"SELECT * FROM virtual_file_path"

    if parent_uid or file_uid:
        query += " WHERE "

    if parent_uid and not file_uid:
        query += f"parent_uid = '{parent_uid}'"
    elif file_uid and not parent_uid:
        query += f"file_uid = '{file_uid}'"
    elif file_uid and parent_uid:
        query += f"parent_uid = '{parent_uid}' AND file_uid = '{file_uid}'"

    result: list = psycopgw.get_query_data(
        query=query, dbname=config_db['database'], user=config_db['ro-user'], password=config_db['ro-pw'],
        host=config_db['server'], port=config_db['port'], leave_connected=True)

    return result

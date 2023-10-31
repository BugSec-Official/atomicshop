from ...psycopgw import psycopgw


def get_analysis(config_db: dict, uid: str = None):
    """
    Get analysis of the UID from a firmware UID.
    :param config_db: dict, database config data.
    :param uid: string, firmware UID. If None, get all the UIDs.

    :return: list, analysis of the UID.
    """

    if uid is None:
        query = f"SELECT * FROM analysis"
    else:
        query = f"SELECT * FROM analysis WHERE uid = '{uid}'"

    result: list = psycopgw.get_query_data(
        query=query, dbname=config_db['database'], user=config_db['ro-user'], password=config_db['ro-pw'],
        host=config_db['server'], port=config_db['port'], leave_connected=True)

    return result

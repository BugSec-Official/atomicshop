from ...psycopgw import psycopgw


def get_fw_uids(config_db: dict, uid: str = None, get_only_uids: bool = True):
    """
    Get all the files UIDs from a firmware UID. These are only the top included files, these are all the files that
    are included in the firmware - files inside the files.

    This function is not applicable for file_objects, only for the firmware containers.
    If you execute it on file_object, it will return empty.

    :param config_db: dict, database config data.
    :param uid: string, firmware UID. If None, get all the UIDs.
    :param get_only_uids: bool, get only the UIDs, not the dictionaries.

    :return: list, included UIDs.
    """

    if uid is None:
        query = f"SELECT * FROM fw_files"
    else:
        query = f"SELECT * FROM fw_files WHERE root_uid = '{uid}'"

    included_uids: list = psycopgw.get_query_data(
        query=query, dbname=config_db['database'], user=config_db['ro-user'], password=config_db['ro-pw'],
        host=config_db['server'], port=config_db['port'], leave_connected=True)

    if get_only_uids:
        # Get only the list of included UIDs, not the dictionaries.
        included_uids = [included_uid['file_uid'] for included_uid in included_uids]

    return included_uids

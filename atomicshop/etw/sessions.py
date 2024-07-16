from ..wrappers.ctyping.etw_winapi import etw_functions


def stop_and_delete(session_name) -> tuple[bool, int]:
    """
    Stop and delete ETW session.

    :param session_name: The name of the session to stop and delete.
    :return: A tuple containing a boolean indicating success and an integer status code.
        True, 0: If the session was stopped and deleted successfully.
        False, <status>: If the session could not be stopped and deleted and the status code, why it failed.
    """

    return etw_functions.stop_and_delete_etw_session(session_name)

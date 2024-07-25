from ..wrappers.ctyping.etw_winapi import etw_functions


def stop_and_delete(session_name: str) -> tuple[bool, int]:
    """
    Stop and delete ETW session.

    :param session_name: The name of the session to stop and delete.
    :return: A tuple containing a boolean indicating success and an integer status code.
        True, 0: If the session was stopped and deleted successfully.
        False, <status>: If the session could not be stopped and deleted and the status code, why it failed.
    """

    return etw_functions.stop_and_delete_etw_session(session_name)


def get_running_list() -> list[dict]:
    """
    List all running ETW sessions.

    :return: A list of strings containing the names of all running ETW sessions.
    """

    return etw_functions.list_etw_sessions()


def is_session_running(session_name: str) -> bool:
    """
    Check if an ETW session is running.

    :param session_name: The name of the session to check.
    :return: A boolean indicating if the session is running.
    """

    # Get all running sessions.
    running_sessions = get_running_list()

    # Check if the session is in the list of running sessions.
    for session in running_sessions:
        if session['session_name'] == session_name:
            return True

    return False

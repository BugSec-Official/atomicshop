from ...wrappers.psutilw import psutilw
from ...basics import list_of_dicts
from ...print_api import print_api


def _execute_cycle(change_monitor_instance, print_kwargs: dict = None):
    """
    This function executes the cycle of the change monitor: process_running.

    :param change_monitor_instance: Instance of the ChangeMonitor class.

    :return: List of dictionaries with the results of the cycle.
    """

    if print_kwargs is None:
        print_kwargs = dict()

    return_list = list()

    processes = _get_list(change_monitor_instance)

    for process_name in change_monitor_instance.check_object_list:
        result = list_of_dicts.is_value_exist_in_key(processes, 'cmdline', process_name, value_case_insensitive=True)

        # If the process name was found in the list of currently running processes.
        if result:
            message = f"Process [{process_name}] is Running."
            print_api(message, color='green', **print_kwargs)
        # If the process name was not found in the list of currently running processes.
        else:
            message = f"Process [{process_name}] not Running!"
            print_api(message, color='red', **print_kwargs)

            return_list.append(message)

    return return_list


def _get_list(change_monitor_instance):
    """
    The function will get the list of opened network sockets and return only the new ones.

    :param change_monitor_instance: Instance of the ChangeMonitor class.

    :return: list of dicts, of new network sockets.
    """

    if change_monitor_instance.first_cycle:
        # Initialize objects for network monitoring.
        change_monitor_instance.fetch_engine = psutilw.PsutilProcesses()

    return change_monitor_instance.fetch_engine.get_processes_as_list_of_dicts(
        default_keys=True, cmdline_to_string=True)

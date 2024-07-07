from ...wrappers.psutilw import psutilw
from ...basics import list_of_dicts
from ...print_api import print_api


class ProcessRunningCheck:
    """
    Class for process running monitoring.
    """

    def __init__(self, change_monitor_instance):
        self.change_monitor_instance = change_monitor_instance
        self.fetch_engine = psutilw.PsutilProcesses()

    def execute_cycle(self, print_kwargs: dict = None):
        """
        This function executes the cycle of the change monitor: process_running.

        :param print_kwargs: Dictionary with the print arguments.
        :return: List of dictionaries with the results of the cycle.
        """

        return_list = list()

        processes = self._get_list()

        for process_name in self.change_monitor_instance.check_object:
            result = list_of_dicts.is_value_exist_in_key(
                processes, 'cmdline', process_name, value_case_insensitive=True)

            # If the process name was found in the list of currently running processes.
            if result:
                message = f"Process [{process_name}] is Running."
                print_api(message, color='green', **(print_kwargs or {}))
            # If the process name was not found in the list of currently running processes.
            else:
                message = f"Process [{process_name}] not Running!"
                print_api(message, color='red', **(print_kwargs or {}))

                return_list.append(message)

        return return_list

    def _get_list(self):
        """
        The function will get the list of opened network sockets and return only the new ones.

        :return: list of dicts, of new network sockets.
        """

        return self.fetch_engine.get_processes_as_list_of_dicts(
            default_keys=True, cmdline_to_string=True)

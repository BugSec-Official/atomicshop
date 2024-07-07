from pathlib import Path
from typing import Union

from ...wrappers.psutilw import psutilw
from ...basics import list_of_dicts
from ...print_api import print_api
from ... import diff_check


INPUT_FILE_DEFAULT_NAME: str = 'known_connections.txt'


class NetworkCheck:
    """
    Class for network monitoring.
    """

    def __init__(self, change_monitor_instance):
        self.change_monitor_instance = change_monitor_instance
        self.diff_checker: Union[diff_check.DiffChecker, None] = None
        self.fetch_engine = psutilw.PsutilConnections()

        if not change_monitor_instance.input_file_name:
            change_monitor_instance.input_file_name = INPUT_FILE_DEFAULT_NAME
        input_file_path = (
            str(Path(change_monitor_instance.input_directory, change_monitor_instance.input_file_name)))

        diff_checker_display_name = \
            f'{change_monitor_instance.input_file_name}|{change_monitor_instance.object_type}'
        self.diff_checker = diff_check.DiffChecker(
            check_object=list(),  # we will append the list of connection events.
            return_first_cycle=True,
            operation_type='single_object',
            check_object_display_name=diff_checker_display_name,
            input_file_path=input_file_path
        )
        self.diff_checker.initiate_before_action()

    def execute_cycle(self, print_kwargs: dict = None):
        """
        This function executes the cycle of the change monitor: network.

        :param print_kwargs: print_api kwargs.
        :return: List of dictionaries with the results of the cycle.
        """

        return_list = list()

        self._get_list()

        # Check if 'known_domains' list was updated from previous cycle.
        result, message = self.diff_checker.check_list_of_dicts(print_kwargs=print_kwargs)

        if result:
            # Get list of new connections only.
            new_connections_only: list = list_of_dicts.get_difference(result['old'], result['updated'])

            for connection in new_connections_only:
                message = \
                    f"New connection: {connection['name']} | " \
                    f"{connection['dst_ip']}:{connection['dst_port']} | " \
                    f"{connection['family']} | {connection['type']} | {connection['cmdline']}"
                # f"{connection['src_ip']}:{connection['src_port']} -> " \
                print_api(message, color='yellow', **(print_kwargs or {}))

                return_list.append(message)

        return return_list

    def _get_list(self):
        """
        The function will get the list of opened network sockets and return only the new ones.

        :return: list of dicts, of new network sockets.
        """

        # Get all connections (list of dicts), including process name and cmdline.
        connections_list_of_dicts: list = \
            self.fetch_engine.get_connections_with_process_as_list_of_dicts(
                attrs=['name', 'cmdline', 'family', 'type', 'dst_ip', 'dst_port'], skip_empty_dst=True,
                cmdline_to_string=True, remove_duplicates=True)

        # Get list of connections that are not in 'known_connections' list.
        missing_connections_from_cycle: list = list_of_dicts.get_difference(
            self.diff_checker.check_object, connections_list_of_dicts)
        # Add missing new connections to 'known_connections' list.
        self.diff_checker.check_object.extend(missing_connections_from_cycle)

        # Sort list of dicts by process name and then by process cmdline.
        self.diff_checker.check_object = list_of_dicts.sort_by_keys(
            self.diff_checker.check_object, key_list=['cmdline', 'name'], case_insensitive=True)

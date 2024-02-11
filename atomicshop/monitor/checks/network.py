from ...wrappers.psutilw import psutilw
from ...basics import list_of_dicts
from ...print_api import print_api


def _execute_cycle(change_monitor_instance, print_kwargs: dict = None):
    """
    This function executes the cycle of the change monitor: network.

    :param change_monitor_instance: Instance of the ChangeMonitor class.

    :return: List of dictionaries with the results of the cycle.
    """

    if print_kwargs is None:
        print_kwargs = dict()

    return_list = list()

    _get_list(change_monitor_instance)

    change_monitor_instance._set_input_file_path()

    # Check if 'known_domains' list was updated from previous cycle.
    result, message = change_monitor_instance.diff_check_list[0].check_list_of_dicts(print_kwargs=print_kwargs)

    if result:
        # Get list of new connections only.
        new_connections_only: list = list_of_dicts.get_difference(result['old'], result['updated'])

        for connection in new_connections_only:
            message = \
                f"New connection: {connection['name']} | " \
                f"{connection['dst_ip']}:{connection['dst_port']} | " \
                f"{connection['family']} | {connection['type']} | {connection['cmdline']}"
            # f"{connection['src_ip']}:{connection['src_port']} -> " \
            print_api(message, color='yellow', **print_kwargs)

            return_list.append(message)

    return return_list


def _get_list(change_monitor_instance):
    """
    The function will get the list of opened network sockets and return only the new ones.

    :param change_monitor_instance: Instance of the ChangeMonitor class.

    :return: list of dicts, of new network sockets.
    """

    if change_monitor_instance.first_cycle:
        original_name: str = str()

        # Initialize objects for network monitoring.
        change_monitor_instance.fetch_engine = psutilw.PsutilConnections()

        # Change settings for the DiffChecker object.
        change_monitor_instance.diff_check_list[0].return_first_cycle = True

        if change_monitor_instance.generate_input_file_name:
            original_name = 'known_connections'
            # Make path for 'input_file_name'.
            change_monitor_instance.input_file_name = f'{original_name}.txt'

        change_monitor_instance.diff_check_list[0].check_object_display_name = \
            f'{original_name}|{change_monitor_instance.object_type}'

        # Set the 'check_object' to empty list, since we will append the list of DNS events.
        change_monitor_instance.diff_check_list[0].check_object = list()

    # Get all connections (list of dicts), including process name and cmdline.
    connections_list_of_dicts: list = \
        change_monitor_instance.fetch_engine.get_connections_with_process_as_list_of_dicts(
            attrs=['name', 'cmdline', 'family', 'type', 'dst_ip', 'dst_port'], skip_empty_dst=True,
            cmdline_to_string=True, remove_duplicates=True)

    # Get list of connections that are not in 'known_connections' list.
    missing_connections_from_cycle: list = list_of_dicts.get_difference(
        change_monitor_instance.diff_check_list[0].check_object, connections_list_of_dicts)
    # Add missing new connections to 'known_connections' list.
    change_monitor_instance.diff_check_list[0].check_object.extend(missing_connections_from_cycle)

    # Sort list of dicts by process name and then by process cmdline.
    change_monitor_instance.diff_check_list[0].check_object = list_of_dicts.sort_by_keys(
        change_monitor_instance.diff_check_list[0].check_object, key_list=['cmdline', 'name'], case_insensitive=True)

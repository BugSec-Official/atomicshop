from ...etw.dns_trace import DnsTrace
from ...print_api import print_api


def _execute_cycle(change_monitor_instance, print_kwargs: dict = None):
    """
    This function executes the cycle of the change monitor: dns.

    :param change_monitor_instance: Instance of the ChangeMonitor class.

    :return: List of dictionaries with the results of the cycle.
    """

    if print_kwargs is None:
        print_kwargs = dict()

    if change_monitor_instance.first_cycle:
        original_name: str = str()

        # Initialize objects for DNS monitoring.
        change_monitor_instance.fetch_engine = DnsTrace(
            enable_process_poller=True, attrs=['name', 'cmdline', 'domain', 'query_type'])

        # Start DNS monitoring.
        change_monitor_instance.fetch_engine.start()

        # Change settings for the DiffChecker object.
        change_monitor_instance.diff_check_list[0].return_first_cycle = True
        change_monitor_instance.diff_check_list[0].aggregation = True

        if change_monitor_instance.generate_input_file_name:
            original_name = 'known_domains'
            # Make path for 'input_file_name'.
            change_monitor_instance.input_file_name = f'{original_name}.json'

        change_monitor_instance.diff_check_list[0].check_object_display_name = \
            f'{original_name}|{change_monitor_instance.object_type}'

        # Set the 'check_object' to empty list, since we will append the list of DNS events.
        change_monitor_instance.diff_check_list[0].check_object = list()

        # Set the input file path.
        change_monitor_instance._set_input_file_path()

    return_list = list()

    # 'emit()' method is blocking (it uses 'get' of queue instance)
    # will return a dict with current DNS trace event.
    event_dict = change_monitor_instance.fetch_engine.emit()

    change_monitor_instance.diff_check_list[0].check_object = [event_dict]

    # if event_dict not in change_monitor_instance.diff_check_list[0].check_object:
    #     change_monitor_instance.diff_check_list[0].check_object.append(event_dict)
    #
    # # Sort list of dicts by process name and then by process cmdline.
    # change_monitor_instance.diff_check_list[0].check_object = list_of_dicts.sort_by_keys(
    #     change_monitor_instance.diff_check_list[0].check_object, ['cmdline', 'name'], case_insensitive=True)

    # Check if 'known_domains' list was updated from previous cycle.
    result, message = change_monitor_instance.diff_check_list[0].check_list_of_dicts(
        sort_by_keys=['cmdline', 'name'], print_kwargs=print_kwargs)

    if result:
        # Get list of new connections only.
        # new_connections_only: list = list_of_dicts.get_difference(result['old'], result['updated'])

        for connection in result['updated']:
            message = \
                f"New domain: {connection['name']} | " \
                f"{connection['domain']} | {connection['query_type']} | " \
                f"{connection['cmdline']}"
            print_api(message, color='yellow', **print_kwargs)

            return_list.append(message)

    return return_list

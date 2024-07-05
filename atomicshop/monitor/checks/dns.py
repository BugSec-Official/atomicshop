from pathlib import Path

from ...etw.dns_trace import DnsTrace
from ...print_api import print_api
from ...diff_check import DiffChecker


INPUT_FILE_DEFAULT_NAME: str = 'known_domains.json'
INPUT_STATISTICS_FILE_DEFAULT_NAME: str = 'dns_statistics.json'
FETCH_ENGINE: DnsTrace = DnsTrace(enable_process_poller=True, attrs=['name', 'cmdline', 'domain', 'query_type'])
SETTINGS = {}
DIFF_CHECKER_AGGREGATION = DiffChecker(
    check_object=list(),                            # DNS events will be appended to this list.
    return_first_cycle=True,
    operation_type='new_objects'
)
DIFF_CHECKER_STATISTICS = DiffChecker(
    check_object=list(),                            # DNS events will be appended to this list.
    return_first_cycle=True,
    operation_type='hit_statistics',
    hit_statistics_enable_queue=True
)


def setup_check(change_monitor_instance):
    global SETTINGS
    SETTINGS = change_monitor_instance.object_type_settings

    if SETTINGS['alert_always'] and SETTINGS['alert_about_missing_entries_after_learning']:
        raise ValueError(
            "ERROR: [alert_always] and [alert_about_missing_entries_after_learning] cannot be True at the same time.")

    if not change_monitor_instance.input_file_name:
        change_monitor_instance.input_file_name = INPUT_FILE_DEFAULT_NAME
    input_file_path = (
        str(Path(change_monitor_instance.input_directory, change_monitor_instance.input_file_name)))

    if not change_monitor_instance.input_statistics_file_name:
        change_monitor_instance.input_statistics_file_name = INPUT_STATISTICS_FILE_DEFAULT_NAME
    input_statistic_file_path = (
        str(Path(change_monitor_instance.input_directory, change_monitor_instance.input_statistics_file_name)))

    if SETTINGS['learning_mode_create_unique_entries_list']:
        DIFF_CHECKER_AGGREGATION.input_file_write_only = change_monitor_instance.input_file_write_only
        DIFF_CHECKER_AGGREGATION.check_object_display_name = \
            f'{change_monitor_instance.input_file_name}|{change_monitor_instance.object_type}'
        DIFF_CHECKER_AGGREGATION.input_file_path = input_file_path
        DIFF_CHECKER_AGGREGATION.new_objects_hours_then_difference = SETTINGS['learning_hours']

    if SETTINGS['create_alert_statistics']:
        DIFF_CHECKER_STATISTICS.input_file_write_only = change_monitor_instance.input_file_write_only
        DIFF_CHECKER_STATISTICS.check_object_display_name = \
            f'{change_monitor_instance.input_statistics_file_name}|{change_monitor_instance.object_type}'
        DIFF_CHECKER_STATISTICS.input_file_path = input_statistic_file_path
        DIFF_CHECKER_STATISTICS.hit_statistics_input_file_rotation_cycle_hours = SETTINGS['statistics_rotation_hours']

    # Start DNS monitoring.
    FETCH_ENGINE.start()


def execute_cycle(print_kwargs: dict = None) -> list:
    """
    This function executes the cycle of the change monitor: dns.
    The function is blocking so while using it, the script will wait for the next DNS event.
    No need to use 'time.sleep()'.

    :param print_kwargs: print_api kwargs.
    :return: List of dictionaries with the results of the cycle.
    """

    # 'emit()' method is blocking (it uses 'get' of queue instance)
    # will return a dict with current DNS trace event.
    event_dict = FETCH_ENGINE.emit()

    return_list = list()
    if SETTINGS['learning_mode_create_unique_entries_list']:
        _aggregation_process(event_dict, return_list, print_kwargs)

    if SETTINGS['create_alert_statistics'] and SETTINGS['alert_always']:
        _statistics_process(event_dict, return_list, print_kwargs)

    return return_list


def _aggregation_process(event_dict: dict, return_list: list, print_kwargs: dict = None):
    DIFF_CHECKER_AGGREGATION.check_object = [event_dict]

    # Check if 'known_domains' list was updated from previous cycle.
    result, message = DIFF_CHECKER_AGGREGATION.check_list_of_dicts(
        sort_by_keys=['cmdline', 'name'], print_kwargs=print_kwargs)

    if result:
        # Check if 'updated' key is in the result. This means that this is a regular cycle.
        if 'updated' in result:
            if not result['time_passed']:
                # Get list of new connections only.
                # new_connections_only: list = list_of_dicts.get_difference(result['old'], result['updated'])

                for connection in result['updated']:
                    message = \
                        f"[Learning] New Domain Added: {connection['name']} | " \
                        f"{connection['domain']} | {connection['query_type']} | " \
                        f"{connection['cmdline']}"
                    print_api(message, color='yellow', **(print_kwargs or {}))

                    return_list.append(message)

        # Check if learning time passed, so we can alert the new entries.
        if 'time_passed' in result:
            if result['time_passed']:
                _statistics_process(result['updated'], return_list, print_kwargs)


def _statistics_process(event_dict: dict, return_list: list, print_kwargs: dict = None):
    DIFF_CHECKER_STATISTICS.check_object = [event_dict]

    # Check if 'known_domains' list was updated from previous cycle.
    result, message = DIFF_CHECKER_STATISTICS.check_list_of_dicts(
        sort_by_keys=['cmdline', 'name'], print_kwargs=print_kwargs)

    if result:
        if 'count' in result:
            message = f"[Alert] DNS Request: {result['entry']} | Times hit: {result['count']}"
            print_api(message, color='yellow', **(print_kwargs or {}))

            return_list.append(message)

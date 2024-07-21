from pathlib import Path
from typing import Union

from ...etws.traces import trace_dns
from ...print_api import print_api
from ...import diff_check


INPUT_FILE_DEFAULT_NAME: str = 'known_domains.json'
INPUT_STATISTICS_FILE_DEFAULT_NAME: str = 'dns_statistics.json'


class DnsCheck:
    """
    Class for DNS monitoring.
    """
    
    def __init__(self, change_monitor_instance):
        self.change_monitor_instance = change_monitor_instance
        self.diff_checker_aggregation: Union[diff_check.DiffChecker, None] = None
        self.diff_checker_statistics: Union[diff_check.DiffChecker, None] = None
        self.settings: dict = change_monitor_instance.object_type_settings

        self.etw_session_name: str = change_monitor_instance.etw_session_name

        self.fetch_engine: trace_dns.DnsRequestResponseTrace = (
            trace_dns.DnsRequestResponseTrace(
                attrs=['name', 'cmdline', 'domain', 'query_type'],
                session_name=self.etw_session_name,
                close_existing_session_name=True
            )
        )

        if self.settings['alert_always'] and self.settings['alert_about_missing_entries_after_learning']:
            raise ValueError(
                "ERROR: [alert_always] and [alert_about_missing_entries_after_learning] "
                "cannot be True at the same time.")
    
        if not change_monitor_instance.input_file_name:
            change_monitor_instance.input_file_name = INPUT_FILE_DEFAULT_NAME
        input_file_path = (
            str(Path(change_monitor_instance.input_directory, change_monitor_instance.input_file_name)))
    
        if not change_monitor_instance.input_statistics_file_name:
            change_monitor_instance.input_statistics_file_name = INPUT_STATISTICS_FILE_DEFAULT_NAME
        input_statistic_file_path = (
            str(Path(change_monitor_instance.input_directory, change_monitor_instance.input_statistics_file_name)))
    
        if self.settings['learning_mode_create_unique_entries_list']:
            aggregation_display_name = \
                f'{change_monitor_instance.input_file_name}|{change_monitor_instance.object_type}'
            self.diff_checker_aggregation = diff_check.DiffChecker(
                check_object=list(),                            # DNS events will be appended to this list.
                return_first_cycle=True,
                operation_type='new_objects',
                input_file_write_only=change_monitor_instance.input_file_write_only,
                check_object_display_name=aggregation_display_name,
                input_file_path=input_file_path,
                new_objects_hours_then_difference=self.settings['learning_hours']
            )
            self.diff_checker_aggregation.initiate_before_action()

        if self.settings['create_alert_statistics']:
            statistics_display_name = \
                f'{change_monitor_instance.input_statistics_file_name}|{change_monitor_instance.object_type}'

            self.diff_checker_statistics = diff_check.DiffChecker(
                check_object=list(),  # DNS events will be appended to this list.
                return_first_cycle=True,
                operation_type='hit_statistics',
                hit_statistics_enable_queue=True,
                input_file_write_only=change_monitor_instance.input_file_write_only,
                check_object_display_name=statistics_display_name,
                input_file_path=input_statistic_file_path,
                hit_statistics_input_file_rotation_cycle_hours=self.settings['statistics_rotation_hours']
            )
            self.diff_checker_statistics.initiate_before_action()
    
        # Start DNS monitoring.
        self.fetch_engine.start()

    def execute_cycle(self, print_kwargs: dict = None) -> list:
        """
        This function executes the cycle of the change monitor: dns.
        The function is blocking so while using it, the script will wait for the next DNS event.
        No need to use 'time.sleep()'.
    
        :param print_kwargs: print_api kwargs.
        :return: List of dictionaries with the results of the cycle.
        """
    
        # 'emit()' method is blocking (it uses 'get' of queue instance)
        # will return a dict with current DNS trace event.
        event_dict = self.fetch_engine.emit()
    
        return_list = list()
        if self.settings['learning_mode_create_unique_entries_list']:
            self._aggregation_process(event_dict, return_list, print_kwargs)
    
        if self.settings['create_alert_statistics'] and self.settings['alert_always']:
            self._statistics_process(event_dict, return_list, print_kwargs)
    
        return return_list

    def _aggregation_process(self, event_dict: dict, return_list: list, print_kwargs: dict = None):
        self.diff_checker_aggregation.check_object = [event_dict]

        # Check if 'known_domains' list was updated from previous cycle.
        result, message = self.diff_checker_aggregation.check_list_of_dicts(
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
                    self._statistics_process(result['updated'], return_list, print_kwargs)
    
    def _statistics_process(self, event_dict: dict, return_list: list, print_kwargs: dict = None):
        self.diff_checker_statistics.check_object = [event_dict]
    
        # Check if 'known_domains' list was updated from previous cycle.
        result, message = self.diff_checker_statistics.check_list_of_dicts(
            sort_by_keys=['cmdline', 'name'], print_kwargs=print_kwargs)
    
        if result:
            if 'count' in result:
                message = f"[Alert] DNS Request: {result['entry']} | Times hit: {result['count']}"
                print_api(message, color='yellow', **(print_kwargs or {}))
    
                return_list.append(message)

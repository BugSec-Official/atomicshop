import datetime

from ... import datetimes


def get_the_last_day_number(statistics_content: list, stop_after_lines: int = None) -> int:
    """
    This function gets the last day number from the statistics content.

    :param statistics_content: list, of lines in the statistics content.
    :param stop_after_lines: integer, if specified, the function will stop after the specified number of lines.
    :return: integer, the last day number.
    """

    last_day_number = None
    start_time_temp = None
    for line_index, line in enumerate(statistics_content):
        try:
            request_time = datetime.datetime.strptime(line['request_time_sent'], '%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            continue

        if not start_time_temp:
            start_time_temp = request_time

        if stop_after_lines:
            if line_index == stop_after_lines:
                break

        last_day_number = datetimes.get_difference_between_dates_in_days(start_time_temp, request_time)
    return last_day_number


def create_empty_features_dict() -> dict:
    """
    This function creates an empty dictionary for the daily stats. This should be initiated for each 'host_type' of:
        'domain', 'subdomain', 'url_no_parameters'.
    :return: dict
    """

    return {
        'total_count': {}, 'normal_count': {}, 'error_count': {},
        'request_0_byte_count': {}, 'response_0_byte_count': {},
        'request_sizes_list': {}, 'response_sizes_list': {},
        'request_sizes_no_0_bytes_list': {}, 'response_sizes_no_0_bytes_list': {},
        'average_request_size': {}, 'average_response_size': {},
        'average_request_size_no_0_bytes': {}, 'average_response_size_no_0_bytes': {}}


def add_to_count_to_daily_stats(
        daily_stats: dict, current_day: int, last_day: int, host_type: str, feature: str, host_name: str) -> None:
    """
    This function adds 1 to the 'count' feature of the current day in the daily stats.

    :param daily_stats: dict, the daily statistics dict.
    :param current_day: integer, the current day number.
    :param last_day: integer, the last day number.
    :param host_type: string, the type of the host. Can be: 'domain', 'subdomain', 'url_no_parameters'.
    :param feature: string, the feature to add the count to. Can be: 'total_count', 'normal_count', 'error_count',
        'request_0_byte_count', 'response_0_byte_count'.
    :param host_name: string, the name of the host.

    :return: None.
    """

    # Aggregate daily domain hits.
    if host_name not in daily_stats[host_type][feature].keys():
        daily_stats[host_type][feature][host_name] = {}
        # Iterate from first day to the last day.
        for day in range(0, last_day + 1):
            daily_stats[host_type][feature][host_name][day] = 0

    # Add count to current day.
    daily_stats[host_type][feature][host_name][current_day] += 1


def add_to_list_to_daily_stats(
        daily_stats: dict, current_day: int, last_day: int, host_type: str, feature: str, host_name: str,
        size: float) -> None:
    """
    This function adds the 'size' to the 'feature' list of the current day in the daily stats.

    :param daily_stats: dict, the daily statistics dict.
    :param current_day: integer, the current day number.
    :param last_day: integer, the last day number.
    :param host_type: string, the type of the host. Can be: 'domain', 'subdomain', 'url_no_parameters'.
    :param feature: string, the feature to add the count to. Can be: 'request_sizes_list', 'response_sizes_list',
        'request_sizes_no_0_bytes_list', 'response_sizes_no_0_bytes_list'.
    :param host_name: string, the name of the host.
    :param size: float, the size in bytes to add to the list.

    :return: None.
    """

    # Aggregate daily domain hits.
    if host_name not in daily_stats[host_type][feature].keys():
        daily_stats[host_type][feature][host_name] = {}
        # Iterate from first day to the last day.
        for day in range(0, last_day + 1):
            daily_stats[host_type][feature][host_name][day] = []

    # Add count to current day.
    daily_stats[host_type][feature][host_name][current_day].append(size)


def add_to_average_to_daily_stats(
        daily_stats: dict, current_day: int, last_day: int, host_type: str, feature: str, host_name: str,
        list_of_sizes: list) -> None:
    """
    This function adds the average size in bytes calculated from the 'list_of_sizes' to the 'feature' of the current
        day in the daily stats.

    :param daily_stats: dict, the daily statistics dict.
    :param current_day: integer, the current day number.
    :param last_day: integer, the last day number.
    :param host_type: string, the type of the host. Can be: 'domain', 'subdomain', 'url_no_parameters'.
    :param feature: string, the feature to add the count to. Can be: 'average_request_size', 'average_response_size',
        'average_request_size_no_0_bytes', 'average_response_size_no_0_bytes'.
    :param host_name: string, the name of the host.
    :param list_of_sizes: list, the list of sizes to calculate the average from.

    :return: None.
    """

    # Aggregate daily domain hits.
    if host_name not in daily_stats[host_type][feature].keys():
        daily_stats[host_type][feature][host_name] = {}
        # Iterate from first day to the last day.
        for day in range(0, last_day + 1):
            daily_stats[host_type][feature][host_name][day] = 0

    # If the list of size is empty, add 0 to the average, since we cannot divide by 0.
    if len(list_of_sizes) == 0:
        daily_stats[host_type][feature][host_name][current_day] = 0
    else:
        daily_stats[host_type][feature][host_name][current_day] = sum(list_of_sizes) / len(list_of_sizes)

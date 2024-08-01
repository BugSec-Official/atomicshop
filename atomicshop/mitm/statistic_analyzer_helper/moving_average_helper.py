import statistics
from typing import Literal

from ...print_api import print_api
from ...wrappers.loggingw import reading, consts
from ...file_io import csvs


def calculate_moving_average(
        file_path: str,
        moving_average_window_days,
        top_bottom_deviation_percentage: float,
        get_deviation_for_last_day_only: bool = False,
        print_kwargs: dict = None
) -> list:
    """
    This function calculates the moving average of the daily statistics.

    :param file_path: string, the path to the 'statistics.csv' file.
    :param moving_average_window_days: integer, the window size for the moving average.
    :param top_bottom_deviation_percentage: float, the percentage of deviation from the moving average to the top or
        bottom.
    :param get_deviation_for_last_day_only: bool, if True, only the last day will be analyzed.
        Example: With 'moving_average_window_days=5', the last 6 days will be analyzed.
        5 days for moving average and the last day for deviation.
        File names example:
            statistics_2021-01-01.csv
            statistics_2021-01-02.csv
            statistics_2021-01-03.csv
            statistics_2021-01-04.csv
            statistics_2021-01-05.csv
            statistics_2021-01-06.csv
        Files 01 to 05 will be used for moving average and the file 06 for deviation.
        Meaning the average calculated for 2021-01-06 will be compared to the values moving average of 2021-01-01
        to 2021-01-05.
    :param print_kwargs: dict, the print_api arguments.
    """

    date_pattern: str = consts.DEFAULT_ROTATING_SUFFIXES_FROM_WHEN['midnight']

    # Get all the file paths and their midnight rotations.
    logs_paths: list = reading.get_logs_paths(
        log_file_path=file_path,
        date_pattern=date_pattern
    )

    if get_deviation_for_last_day_only:
        days_back_to_analyze: int = moving_average_window_days + 1
        logs_paths = logs_paths[-days_back_to_analyze:]

    statistics_content: dict = {}
    # Read each file to its day.
    for log_path_dict in logs_paths:
        date_string = log_path_dict['date_string']
        statistics_content[date_string] = {}

        statistics_content[date_string]['file'] = log_path_dict

        log_file_content, log_file_header = (
            csvs.read_csv_to_list_of_dicts_by_header(log_path_dict['file_path'], **(print_kwargs or {})))
        statistics_content[date_string]['content'] = log_file_content
        statistics_content[date_string]['header'] = log_file_header

        statistics_content[date_string]['content_no_errors'] = get_content_without_errors(log_file_content)

        # Get the data dictionary from the statistics content.
        statistics_content[date_string]['statistics_daily'] = compute_statistics_from_content(
            statistics_content[date_string]['content_no_errors']
        )

    moving_average_dict: dict = compute_moving_averages_from_average_statistics(
        statistics_content,
        moving_average_window_days
    )

    # Add the moving average to the statistics content.
    for day, day_dict in statistics_content.items():
        try:
            day_dict['moving_average'] = moving_average_dict[day]
        except KeyError:
            day_dict['moving_average'] = {}

    # Find deviation from the moving average to the bottom or top by specified percentage.
    deviation_list: list = find_deviation_from_moving_average(
        statistics_content, top_bottom_deviation_percentage)

    return deviation_list


def get_content_without_errors(content: list) -> list:
    """
    This function gets the 'statistics.csv' file content without errors from the 'content' list.

    :param content: list, the content list.
    :return: list, the content without errors.
    """

    traffic_statistics_without_errors: list = []
    for line in content:
        # Skip empty lines, headers and errors.
        if line['host'] == 'host' or line['command'] == '':
            continue

        traffic_statistics_without_errors.append(line)

    return traffic_statistics_without_errors


def get_data_dict_from_statistics_content(content: list) -> dict:
    """
    This function gets the data dictionary from the 'statistics.csv' file content.

    :param content: list, the content list.
    :return: dict, the data dictionary.
    """

    hosts_requests_responses: dict = {}
    for line in content:
        # If subdomain is not in the dictionary, add it.
        if line['host'] not in hosts_requests_responses:
            hosts_requests_responses[line['host']] = {
                'request_sizes': [],
                'response_sizes': []
            }

        # Append the sizes.
        try:
            hosts_requests_responses[line['host']]['request_sizes'].append(int(line['request_size_bytes']))
            hosts_requests_responses[line['host']]['response_sizes'].append(
                int(line['response_size_bytes']))
        except ValueError:
            print_api(line, color='yellow')
            raise

    return hosts_requests_responses


def compute_statistics_from_data_dict(data_dict: dict):
    """
    This function computes the statistics from the data dictionary.

    :param data_dict: dict, the data dictionary.
    :return: dict, the statistics dictionary.
    """

    for host, host_dict in data_dict.items():
        count = len(host_dict['request_sizes'])
        avg_request_size = statistics.mean(host_dict['request_sizes']) if count > 0 else 0
        median_request_size = statistics.median(host_dict['request_sizes']) if count > 0 else 0
        avg_response_size = statistics.mean(host_dict['response_sizes']) if count > 0 else 0
        median_response_size = statistics.median(host_dict['response_sizes']) if count > 0 else 0

        data_dict[host]['count'] = count
        data_dict[host]['avg_request_size'] = avg_request_size
        data_dict[host]['median_request_size'] = median_request_size
        data_dict[host]['avg_response_size'] = avg_response_size
        data_dict[host]['median_response_size'] = median_response_size


def compute_statistics_from_content(content: list):
    """
    This function computes the statistics from the 'statistics.csv' file content.

    :param content: list, the content list.
    :return: dict, the statistics dictionary.
    """

    hosts_requests_responses: dict = get_data_dict_from_statistics_content(content)
    compute_statistics_from_data_dict(hosts_requests_responses)

    return hosts_requests_responses


def compute_moving_averages_from_average_statistics(
        average_statistics_dict: dict,
        moving_average_window_days: int
):
    """
    This function computes the moving averages from the average statistics dictionary.

    :param average_statistics_dict: dict, the average statistics dictionary.
    :param moving_average_window_days: integer, the window size for the moving average.
    :return: dict, the moving averages' dictionary.
    """

    moving_average: dict = {}
    for day_index, (day, day_dict) in enumerate(average_statistics_dict.items()):
        current_day = day_index + 1
        if current_day < moving_average_window_days:
            continue

        # Create list of the last 'moving_average_window_days' days, including the current day.
        last_x_window_days_content_list = (
            list(average_statistics_dict.values()))[current_day-moving_average_window_days:current_day]

        # Compute the moving averages.
        moving_average[day] = compute_average_for_current_day_from_past_x_days(last_x_window_days_content_list)

    return moving_average


def compute_average_for_current_day_from_past_x_days(previous_days_content_list: list) -> dict:
    """
    This function computes the average for the current day from the past x days.

    :param previous_days_content_list: list, the list of the previous days content.
    :return: dict, the average dictionary.
    """

    moving_average: dict = {}
    for entry in previous_days_content_list:
        statistics_daily = entry['statistics_daily']
        for host, host_dict in statistics_daily.items():
            if host not in moving_average:
                moving_average[host] = {
                    'counts': [],
                    'avg_request_sizes': [],
                    'avg_response_sizes': [],
                }

            moving_average[host]['counts'].append(int(host_dict['count']))
            moving_average[host]['avg_request_sizes'].append(float(host_dict['avg_request_size']))
            moving_average[host]['avg_response_sizes'].append(float(host_dict['avg_response_size']))

    # Compute the moving average.
    moving_average_results: dict = {}
    for host, host_dict in moving_average.items():
        ma_count = statistics.mean(host_dict['counts'])
        ma_request_size = statistics.mean(host_dict['avg_request_sizes'])
        ma_response_size = statistics.mean(host_dict['avg_response_sizes'])

        moving_average_results[host] = {
            'ma_count': ma_count,
            'ma_request_size': ma_request_size,
            'ma_response_size': ma_response_size,
            'counts': host_dict['counts'],
            'avg_request_sizes': host_dict['avg_request_sizes'],
            'avg_response_sizes': host_dict['avg_response_sizes']
        }

    return moving_average_results


def find_deviation_from_moving_average(
        statistics_content: dict,
        top_bottom_deviation_percentage: float
) -> list:
    """
    This function finds the deviation from the moving average to the bottom or top by specified percentage.

    :param statistics_content: dict, the statistics content dictionary.
    :param top_bottom_deviation_percentage: float, the percentage of deviation from the moving average to the top or
        bottom.
    :return: list, the deviation list.
    """

    def _check_deviation(
            check_type: Literal['count', 'avg_request_size', 'avg_response_size'],
            ma_check_type: Literal['ma_count', 'ma_request_size', 'ma_response_size'],
            day_statistics_content_dict: dict,
            moving_averages_dict: dict
    ):
        """
        This function checks the deviation for the host.
        """

        nonlocal message

        host_moving_average_by_type = moving_averages_dict[host][ma_check_type]
        check_type_moving_by_percent = (
                host_moving_average_by_type * top_bottom_deviation_percentage)
        check_type_moving_above = host_moving_average_by_type + check_type_moving_by_percent
        check_type_moving_below = host_moving_average_by_type - check_type_moving_by_percent

        deviation_type = None
        if day_statistics_content_dict[check_type] > check_type_moving_above:
            deviation_type = 'above'
        elif day_statistics_content_dict[check_type] < check_type_moving_below:
            deviation_type = 'below'

        if deviation_type:
            message = f'[{check_type}] is [{deviation_type}] the moving average.'
            deviation_list.append({
                'day': day,
                'host': host,
                'message': message,
                'value': day_statistics_content_dict[check_type],
                'ma_value': host_moving_average_by_type,
                'check_type': check_type,
                'percentage': top_bottom_deviation_percentage,
                'ma_value_checked': check_type_moving_above,
                'deviation_type': deviation_type,
                'data': day_statistics_content_dict,
                'ma_data': moving_averages_dict[host]
            })

    deviation_list: list = []
    for day_index, (day, day_dict) in enumerate(statistics_content.items()):
        # If it's the first day, there is no previous day moving average.
        if day_index == 0:
            previous_day_moving_average_dict = {}
        else:
            previous_day_moving_average_dict = list(statistics_content.values())[day_index-1].get('moving_average', {})

        # If there is no moving average for previous day continue to the next day.
        if not previous_day_moving_average_dict:
            continue

        for host, host_dict in day_dict['statistics_daily'].items():
            # If the host is not in the moving averages, then this is clear deviation.
            # It means that in the current day, there were no requests for this host.
            if host not in previous_day_moving_average_dict:
                message = f'Host not in the moving averages: {host}'
                deviation_list.append({
                    'day': day,
                    'host': host,
                    'data': host_dict,
                    'message': message,
                    'type': 'clear'
                })
                continue

            _check_deviation(
                'count', 'ma_count', host_dict, previous_day_moving_average_dict)
            _check_deviation(
                'avg_request_size', 'ma_request_size', host_dict, previous_day_moving_average_dict)
            _check_deviation(
                'avg_response_size', 'ma_response_size', host_dict, previous_day_moving_average_dict)

    return deviation_list

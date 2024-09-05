import statistics
from pathlib import Path
from typing import Literal

from ...print_api import print_api
from ...wrappers.loggingw import reading, consts
from ...file_io import csvs
from ... import urls, filesystem


def calculate_moving_average(
        file_path: str,
        by_type: Literal['host', 'url'],
        moving_average_window_days,
        top_bottom_deviation_percentage: float,
        get_deviation_for_last_day_only: bool = False,
        skip_total_count_less_than: int = None,
        print_kwargs: dict = None
) -> list:
    """
    This function calculates the moving average of the daily statistics.

    :param file_path: string, the path to the 'statistics.csv' file.
    :param by_type: string, the type to calculate the moving average by. Can be 'host' or 'url'.
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
    :param skip_total_count_less_than: integer, if the total count is less than this number, skip the deviation.
    :param print_kwargs: dict, the print_api arguments.
    """

    date_format: str = consts.DEFAULT_ROTATING_SUFFIXES_FROM_WHEN['midnight']

    # Get all the file paths and their midnight rotations.
    logs_paths: list[filesystem.AtomicPath] = reading.get_logs_paths(
        log_file_path=file_path,
        date_format=date_format
    )

    if get_deviation_for_last_day_only:
        days_back_to_analyze: int = moving_average_window_days + 1
        logs_paths = logs_paths[-days_back_to_analyze:]

    statistics_content: dict = {}
    # Read each file to its day.
    for log_atomic_path in logs_paths:
        date_string: str = log_atomic_path.datetime_string
        statistics_content[date_string] = {}

        statistics_content[date_string]['file'] = log_atomic_path

        log_file_content, log_file_header = (
            csvs.read_csv_to_list_of_dicts_by_header(log_atomic_path.path, **(print_kwargs or {})))
        statistics_content[date_string]['content'] = log_file_content
        statistics_content[date_string]['header'] = log_file_header

        statistics_content[date_string]['content_no_useless'] = get_content_without_useless(log_file_content)

        # Get the data dictionary from the statistics content.
        statistics_content[date_string]['statistics_daily'] = compute_statistics_from_content(
            statistics_content[date_string]['content_no_useless'], by_type)

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
        statistics_content, top_bottom_deviation_percentage, skip_total_count_less_than)

    return deviation_list


def get_content_without_useless(content: list) -> list:
    """
    This function gets the 'statistics.csv' file content without errors from the 'content' list.

    :param content: list, the content list.
    :return: list, the content without errors.
    """

    traffic_statistics_without_errors: list = []
    for line in content:
        # Skip empty lines, headers and errors.
        if line['host'] == 'host' or (line['request_size_bytes'] == '' and line['response_size_bytes'] == ''):
            continue

        traffic_statistics_without_errors.append(line)

    return traffic_statistics_without_errors


def get_data_dict_from_statistics_content(
        content: list,
        by_type: Literal['host', 'url']
) -> dict:
    """
    This function gets the data dictionary from the 'statistics.csv' file content.

    :param content: list, the content list.
    :param by_type: string, the type to calculate the moving average by. Can be 'host' or 'url'.
    :return: dict, the data dictionary.
    """

    hosts_requests_responses: dict = {}
    for line in content:
        if by_type == 'host':
            type_to_check: str = line['host']
        elif by_type == 'url':
            # Combine host and path to URL.
            type_to_check: str = line['host'] + line['path']
            # Remove the parameters from the URL.
            url_parsed = urls.url_parser(type_to_check)

            if url_parsed['file'] and Path(url_parsed['file']).suffix in ['.gz', '.gzip', '.zip']:
                type_to_check = '/'.join(url_parsed['directories'][:-1])
            else:
                type_to_check = url_parsed['path']

            # Remove the last slash from the URL.
            type_to_check = type_to_check.removesuffix('/')
        else:
            raise ValueError(f'Invalid by_type: {by_type}')

        # If subdomain is not in the dictionary, add it.
        if type_to_check not in hosts_requests_responses:
            hosts_requests_responses[type_to_check] = {
                'request_sizes': [],
                'response_sizes': []
            }

        # Append the sizes.
        try:
            request_size_bytes = line['request_size_bytes']
            response_size_bytes = line['response_size_bytes']
            if request_size_bytes != '':
                hosts_requests_responses[type_to_check]['request_sizes'].append(int(request_size_bytes))
            if response_size_bytes != '':
                hosts_requests_responses[type_to_check]['response_sizes'].append(int(response_size_bytes))
        except ValueError as e:
            print_api(line, color='yellow')
            raise e

    return hosts_requests_responses


def compute_statistics_from_data_dict(data_dict: dict):
    """
    This function computes the statistics from the data dictionary.

    :param data_dict: dict, the data dictionary.
    :return: dict, the statistics dictionary.
    """

    for host, host_dict in data_dict.items():
        count_requests = len(host_dict['request_sizes'])
        count_responses = len(host_dict['response_sizes'])
        avg_request_size = statistics.mean(host_dict['request_sizes']) if count_requests > 0 else 0
        median_request_size = statistics.median(host_dict['request_sizes']) if count_requests > 0 else 0
        avg_response_size = statistics.mean(host_dict['response_sizes']) if count_responses > 0 else 0
        median_response_size = statistics.median(host_dict['response_sizes']) if count_responses > 0 else 0

        data_dict[host]['count_requests'] = count_requests
        data_dict[host]['count_responses'] = count_responses
        data_dict[host]['avg_request_size'] = avg_request_size
        data_dict[host]['median_request_size'] = median_request_size
        data_dict[host]['avg_response_size'] = avg_response_size
        data_dict[host]['median_response_size'] = median_response_size


def compute_statistics_from_content(
        content: list,
        by_type: Literal['host', 'url']
):
    """
    This function computes the statistics from the 'statistics.csv' file content.

    :param content: list, the content list.
    :param by_type: string, the type to calculate the moving average by. Can be 'host' or 'url'.
    :return: dict, the statistics dictionary.
    """

    requests_responses: dict = get_data_dict_from_statistics_content(content, by_type)
    compute_statistics_from_data_dict(requests_responses)

    return requests_responses


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
        moving_average[day] = compute_average_for_current_day_from_past_x_days(
            last_x_window_days_content_list)

    return moving_average


def compute_average_for_current_day_from_past_x_days(
        previous_days_content_list: list
) -> dict:
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
                    'all_request_counts': [],
                    'all_response_counts': [],
                    'avg_request_sizes': [],
                    'avg_response_sizes': [],
                    'median_request_sizes': [],
                    'median_response_sizes': []
                }

            moving_average[host]['all_request_counts'].append(int(host_dict['count_requests']))
            moving_average[host]['all_response_counts'].append(int(host_dict['count_responses']))
            moving_average[host]['avg_request_sizes'].append(float(host_dict['avg_request_size']))
            moving_average[host]['avg_response_sizes'].append(float(host_dict['avg_response_size']))
            moving_average[host]['median_request_sizes'].append(float(host_dict['median_request_size']))
            moving_average[host]['median_response_sizes'].append(float(host_dict['median_response_size']))

    # Compute the moving average.
    moving_average_results: dict = {}
    for host, host_dict in moving_average.items():
        ma_request_count = statistics.mean(host_dict['all_request_counts'])
        ma_response_count = statistics.mean(host_dict['all_response_counts'])
        ma_request_size = statistics.mean(host_dict['avg_request_sizes'])
        ma_response_size = statistics.mean(host_dict['avg_response_sizes'])
        mm_request_count = statistics.median(host_dict['all_request_counts'])
        mm_response_count = statistics.median(host_dict['all_response_counts'])
        mm_request_size = statistics.median(host_dict['median_request_sizes'])
        mm_response_size = statistics.median(host_dict['median_response_sizes'])

        moving_average_results[host] = {
            'ma_request_count': ma_request_count,
            'ma_response_count': ma_response_count,
            'ma_request_size': ma_request_size,
            'ma_response_size': ma_response_size,
            'mm_request_count': mm_request_count,
            'mm_response_count': mm_response_count,
            'mm_request_size': mm_request_size,
            'mm_response_size': mm_response_size,
            'all_request_counts': host_dict['all_request_counts'],
            'all_response_counts': host_dict['all_response_counts'],
            'avg_request_sizes': host_dict['avg_request_sizes'],
            'avg_response_sizes': host_dict['avg_response_sizes'],
            'median_request_sizes': host_dict['median_request_sizes'],
            'median_response_sizes': host_dict['median_response_sizes']
        }

    return moving_average_results


def find_deviation_from_moving_average(
        statistics_content: dict,
        top_bottom_deviation_percentage: float,
        skip_total_count_less_than: int = None
) -> list:
    """
    This function finds the deviation from the moving average to the bottom or top by specified percentage.

    :param statistics_content: dict, the statistics content dictionary.
    :param top_bottom_deviation_percentage: float, the percentage of deviation from the moving average to the top or
        bottom.
    :param skip_total_count_less_than: integer, if the total count is less than this number, skip the deviation.
    :return: list, the deviation list.
    """

    def _check_deviation(
            check: Literal['count', 'avg'],
            traffic_direction: Literal['request', 'response'],
            day_statistics_content_dict: dict,
            moving_averages_dict: dict
    ):
        """
        This function checks the deviation for the host.
        """

        nonlocal message

        if check == 'count':
            check_type = f'{check}_{traffic_direction}s'
            ma_check_type = f'ma_{traffic_direction}_{check}'
            median_type_string = check_type
            moving_median_type_string = f'mm_{traffic_direction}_{check}'
        elif check == 'avg':
            check_type = f'{check}_{traffic_direction}_size'
            ma_check_type = f'ma_{traffic_direction}_size'
            median_type_string = f'median_{traffic_direction}_size'
            moving_median_type_string = f'mm_{traffic_direction}_size'
        else:
            raise ValueError(f'Invalid check: {check}')

        host_moving_average_by_type = moving_averages_dict[host][ma_check_type]
        check_type_moving_by_percent = (
                host_moving_average_by_type * top_bottom_deviation_percentage)
        check_type_moving_above = host_moving_average_by_type + check_type_moving_by_percent
        check_type_moving_below = host_moving_average_by_type - check_type_moving_by_percent

        deviation_type = None
        deviation_percentage = None
        error_message: str = str()
        if day_statistics_content_dict[check_type] > check_type_moving_above:
            deviation_type = 'above'
            try:
                deviation_percentage = (
                        (day_statistics_content_dict[check_type] - host_moving_average_by_type) /
                        host_moving_average_by_type)
            except ZeroDivisionError as e:
                error_message = f' | Error: Division by 0, host_moving_average_by_type: {host_moving_average_by_type}'
        elif day_statistics_content_dict[check_type] < check_type_moving_below:
            deviation_type = 'below'
            deviation_percentage = (
                    (host_moving_average_by_type - day_statistics_content_dict[check_type]) /
                    host_moving_average_by_type)

        if deviation_type:
            message = f'[{check_type}] is [{deviation_type}] the moving average.' + error_message

            # The median and the total count are None for the count, Since they are the count.
            if 'count' in check_type:
                total_entries_averaged = None
                median_size = None
            else:
                total_entries_averaged = day_statistics_content_dict[f'count_{traffic_direction}s']
                median_size = day_statistics_content_dict[median_type_string]

            value = day_statistics_content_dict[check_type]

            # If the total count is less than the specified number, skip the deviation.
            if skip_total_count_less_than:
                if total_entries_averaged:
                    if total_entries_averaged < skip_total_count_less_than:
                        return
                else:
                    if value < skip_total_count_less_than:
                        return

            moving_median_size = moving_averages_dict[host][moving_median_type_string]

            deviation_list.append({
                'day': day,
                'host': host,
                'message': message,
                'value': value,
                'ma_value': host_moving_average_by_type,
                'check_type': check_type,
                'percentage': top_bottom_deviation_percentage,
                'ma_value_checked': check_type_moving_above,
                'deviation_percentage': deviation_percentage,
                'total_entries_averaged': total_entries_averaged,
                'deviation_type': deviation_type,
                'median_size': median_size,
                'mm_size': moving_median_size,
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
                    'message': message,
                    'value': None,
                    'ma_value': None,
                    'check_type': None,
                    'percentage': None,
                    'ma_value_checked': None,
                    'deviation_percentage': None,
                    'total_entries_averaged': None,
                    'deviation_type': 'clear',
                    'median_size': None,
                    'mm_size': None,
                    'data': host_dict,
                    'ma_data': previous_day_moving_average_dict
                })
                continue

            _check_deviation(
                'count', 'request', host_dict, previous_day_moving_average_dict)
            _check_deviation(
                'count', 'response', host_dict, previous_day_moving_average_dict)
            _check_deviation(
                'avg', 'request', host_dict, previous_day_moving_average_dict)
            _check_deviation(
                'avg', 'response', host_dict, previous_day_moving_average_dict)

    return deviation_list

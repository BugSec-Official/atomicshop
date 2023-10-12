import datetime

from .. import filesystem, domains, datetimes, urls
from ..basics import dicts
from ..file_io import tomls, xlsxs
from ..wrappers.loggingw import reading
from ..print_api import print_api


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


def analyze(main_file_path: str):
    """
    This function is the main function for the statistic analyzer.
    :param main_file_path: Path to the main file that is calling this function (__file__).
    :return:
    """

    # Get the config and set variables.
    script_directory: str = filesystem.get_file_directory(main_file_path)
    config_path: str = filesystem.add_object_to_path(script_directory, 'config_stats.toml')
    config: dict = tomls.read_toml_file(config_path)
    summary_path: str = filesystem.check_absolute_path___add_full(config['report_file_path'], script_directory)

    # Get the content from statistics files.
    statistics_content: list = reading.get_logs(
        config['statistic_files_path'], pattern='statistics*.csv', log_type='csv',
    )

    # Initialize loop.
    line_total_count: int = len(statistics_content)
    start_time = None
    last_day_number = None
    overall_stats: dict = {
        'domain': {'total_count': {}, 'normal_count': {}, 'error_count': {}},
        'subdomain': {'total_count': {}, 'normal_count': {}, 'error_count': {}}
    }
    daily_stats: dict = {
        'domain': create_empty_features_dict(),
        'subdomain': create_empty_features_dict(),
        'url_no_parameters': create_empty_features_dict()
    }

    # Start the main loop.
    for line_index, line in enumerate(statistics_content):
        # Converting time string to object.
        # If the time string is not of the specific format, continue to the next line.
        try:
            request_time = datetime.datetime.strptime(line['request_time_sent'], '%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            continue

        if not start_time:
            start_time = request_time

        # For testing, you can set the 'break_after_lines' to an integer, which symbolizes the number of the line
        # of the 'statistics_content' to stop the loop after.
        break_after_lines = None

        # Find the last day number. If 'break_after_lines' is specified, the loop will stop after the specified line.
        if not last_day_number:
            last_day_number = get_the_last_day_number(statistics_content, break_after_lines)

        if break_after_lines:
            if line_index == break_after_lines:
                break

        if config['strings_to_include_in_subdomain'] and config['strings_to_include_in_subdomain'] != ['']:
            # Checking that 'strings_to_include_in_subdomain' are in the subdomain, if not, continue to the next line.
            if not any(string in line['host'] for string in config['strings_to_include_in_subdomain']):
                continue

        if config['strings_to_exclude_from_subdomain'] and config['strings_to_exclude_from_subdomain'] != ['']:
            # Checking that 'strings_to_exclude_from_subdomain' are not in the subdomain, if they are, continue.
            if any(string in line['host'] for string in config['strings_to_exclude_from_subdomain']):
                continue

        # Get the subdomain with the main domain from the 'host' column of current line.
        subdomain = line['host']
        # Get the main domain from the subdomain.
        # Check if suffix of the 'host' is '.com'.
        if line['host'].endswith('.com'):
            # Get only the main domain.
            main_domain = line['host'].split('.')[-2] + '.com'
        # If the suffix is not '.com', use the 'domains' library to get the main domain.
        else:
            # This is the slowest part of the whole loop.
            main_domain = domains.get_registered_domain(line['host'])

        # If the domain is empty, continue to the next line.
        if not main_domain:
            continue

        # If the domain is already in the dict, add 1 to the counter, else add the key to the dict.
        if main_domain in overall_stats['domain']['total_count'].keys():
            overall_stats['domain']['total_count'][main_domain] = (
                    overall_stats['domain']['total_count'][main_domain] + 1)
        else:
            overall_stats['domain']['total_count'][main_domain] = 1

        # If the subdomain is already in the dict, add 1 to the counter, else add the key to the dict.
        if subdomain in overall_stats['subdomain']['total_count'].keys():
            overall_stats['subdomain']['total_count'][subdomain] = (
                    overall_stats['subdomain']['total_count'][subdomain] + 1)
        else:
            # overall_stats['subdomain']['total_count'] = {}
            overall_stats['subdomain']['total_count'][subdomain] = 1

        # Check if there is an error in the line and count the domain under 'error_count' key.
        if line['error'] != '':
            # If the domain is already in the dict, add 1 to the counter, else add the key to the dict.
            if main_domain in overall_stats['domain']['error_count'].keys():
                overall_stats['domain']['error_count'][main_domain] = (
                        overall_stats['domain']['error_count'][main_domain] + 1)
            else:
                # overall_stats['domain']['total_count'] = {}
                overall_stats['domain']['error_count'][main_domain] = 1

            # If the subdomain is already in the dict, add 1 to the counter, else add the key to the dict.
            if subdomain in overall_stats['subdomain']['error_count'].keys():
                overall_stats['subdomain']['error_count'][subdomain] = (
                        overall_stats['subdomain']['error_count'][subdomain] + 1)
            else:
                # overall_stats['subdomain']['total_count'] = {}
                overall_stats['subdomain']['error_count'][subdomain] = 1
        else:
            # If the domain is already in the dict, add 1 to the counter, else add the key to the dict.
            if main_domain in overall_stats['domain']['normal_count'].keys():
                overall_stats['domain']['normal_count'][main_domain] = (
                        overall_stats['domain']['normal_count'][main_domain] + 1)
            else:
                # overall_stats['domain']['total_count'] = {}
                overall_stats['domain']['normal_count'][main_domain] = 1

            # If the subdomain is already in the dict, add 1 to the counter, else add the key to the dict.
            if subdomain in overall_stats['subdomain']['normal_count'].keys():
                overall_stats['subdomain']['normal_count'][subdomain] = (
                        overall_stats['subdomain']['normal_count'][subdomain] + 1)
            else:
                # overall_stats['subdomain']['total_count'] = {}
                overall_stats['subdomain']['normal_count'][subdomain] = 1

        # Get the URL without parameters.
        url = line['host'] + line['path']
        url_no_parameters = urls.url_parser(url)['path']

        # Get the request and response sizes.
        # If the size is not numeric that can be converted to integer, set it to None.
        # Since, probably there was an SSL 'error' in the line.
        try:
            request_size = int(line['request_size_bytes'])
            response_size = int(line['response_size_bytes'])
        except ValueError:
            request_size = None
            response_size = None

        # Start Day aggregation ========================================================================================
        # Daily stats.
        day_number = datetimes.get_difference_between_dates_in_days(start_time, request_time)

        # Add 1 to the total count of the current day.
        add_to_count_to_daily_stats(
            daily_stats, day_number, last_day_number, 'domain', 'total_count', main_domain)
        add_to_count_to_daily_stats(
            daily_stats, day_number, last_day_number, 'subdomain', 'total_count', subdomain)
        add_to_count_to_daily_stats(
            daily_stats, day_number, last_day_number, 'url_no_parameters', 'total_count', url_no_parameters)

        # Handle line if it has error.
        if line['error'] != '':
            add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'domain', 'error_count', main_domain)
            add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'subdomain', 'error_count', subdomain)
            add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'url_no_parameters', 'error_count', url_no_parameters)
        else:
            add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'domain', 'normal_count', main_domain)
            add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'subdomain', 'normal_count', subdomain)
            add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'url_no_parameters', 'normal_count', url_no_parameters)

        if request_size == 0:
            add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'domain', 'request_0_byte_count',
                main_domain)
            add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'subdomain', 'request_0_byte_count',
                subdomain)
            add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'url_no_parameters', 'request_0_byte_count',
                url_no_parameters)

        if response_size == 0:
            add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'domain', 'response_0_byte_count',
                main_domain)
            add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'subdomain', 'response_0_byte_count',
                subdomain)
            add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'url_no_parameters', 'response_0_byte_count',
                url_no_parameters)

        if request_size is not None and response_size is not None:
            add_to_list_to_daily_stats(
                daily_stats, day_number, last_day_number, 'domain', 'request_sizes_list', main_domain, request_size)
            add_to_list_to_daily_stats(
                daily_stats, day_number, last_day_number, 'subdomain', 'request_sizes_list', subdomain, request_size)
            add_to_list_to_daily_stats(
                daily_stats, day_number, last_day_number, 'url_no_parameters', 'request_sizes_list', url_no_parameters,
                request_size)

            add_to_list_to_daily_stats(
                daily_stats, day_number, last_day_number, 'domain', 'response_sizes_list', main_domain, response_size)
            add_to_list_to_daily_stats(
                daily_stats, day_number, last_day_number, 'subdomain', 'response_sizes_list', subdomain, response_size)
            add_to_list_to_daily_stats(
                daily_stats, day_number, last_day_number, 'url_no_parameters', 'response_sizes_list', url_no_parameters,
                response_size)

        if request_size != 0 and request_size is not None:
            add_to_list_to_daily_stats(
                daily_stats, day_number, last_day_number, 'domain', 'request_sizes_no_0_bytes_list',
                main_domain, request_size)
            add_to_list_to_daily_stats(
                daily_stats, day_number, last_day_number, 'subdomain', 'request_sizes_no_0_bytes_list',
                subdomain, request_size)
            add_to_list_to_daily_stats(
                daily_stats, day_number, last_day_number, 'url_no_parameters', 'request_sizes_no_0_bytes_list',
                url_no_parameters, request_size)

        if response_size != 0 and response_size is not None:
            add_to_list_to_daily_stats(
                daily_stats, day_number, last_day_number, 'domain', 'response_sizes_no_0_bytes_list',
                main_domain, response_size)
            add_to_list_to_daily_stats(
                daily_stats, day_number, last_day_number, 'subdomain', 'response_sizes_no_0_bytes_list',
                subdomain, response_size)
            add_to_list_to_daily_stats(
                daily_stats, day_number, last_day_number, 'url_no_parameters', 'response_sizes_no_0_bytes_list',
                url_no_parameters, response_size)

        print_api(f'Processing line: {line_index+1}/{line_total_count}', print_end='\r')

    # Calculate daily average request and response sizes.
    for host_type, features in daily_stats.items():
        for feature, hosts in features.items():
            if feature == 'request_sizes_list':
                feature_name = 'average_request_size'
            elif feature == 'response_sizes_list':
                feature_name = 'average_response_size'
            elif feature == 'request_sizes_no_0_bytes_list':
                feature_name = 'average_request_size_no_0_bytes'
            elif feature == 'response_sizes_no_0_bytes_list':
                feature_name = 'average_response_size_no_0_bytes'
            else:
                continue

            for host_name, days in hosts.items():
                for day, sizes in days.items():
                    add_to_average_to_daily_stats(
                        daily_stats, day, last_day_number, host_type, feature_name, host_name, sizes)

    # Sorting overall stats.
    sorted_overall_stats: dict = {
        'domain': {'total_count': {}, 'normal_count': {}, 'error_count': {}},
        'subdomain': {'total_count': {}, 'normal_count': {}, 'error_count': {}}
    }
    for feature_dict, feature_dict_value in overall_stats.items():
        for feature, feature_value in feature_dict_value.items():
            sorted_overall_stats[feature_dict][feature] = (
                dicts.sort_by_values(feature_value, reverse=True))

    # Create combined dictionary of the sorted statistics to export to XLSX file.
    combined_sorted_stats = {}
    # Add overall stats.
    for feature_dict, feature_dict_value in sorted_overall_stats.items():
        for feature, feature_value in feature_dict_value.items():
            for feature_index, (host_name, counter) in enumerate(feature_value.items()):
                if feature_index == 0:
                    try:
                        combined_sorted_stats[f'overall_stats']['host_name'].append('')
                        combined_sorted_stats[f'overall_stats']['counter'].append('')
                        combined_sorted_stats[f'overall_stats']['host_name'].append(f'{feature_dict}_{feature}')
                        combined_sorted_stats[f'overall_stats']['counter'].append('counter')
                    except KeyError:
                        combined_sorted_stats[f'overall_stats'] = \
                            {f'host_name': [f'{feature_dict}_{feature}'], 'counter': ['counter']}

                combined_sorted_stats[f'overall_stats']['host_name'].append(host_name)
                combined_sorted_stats[f'overall_stats']['counter'].append(counter)

    feature_name = ''
    # Add daily stats to combined dict. Each day will be a column.
    for host_type, features in daily_stats.items():
        for feature, hosts in features.items():
            if 'count' in feature:
                feature_name = 'counts'
            elif 'list' in feature:
                feature_name = 'lists'
            elif 'average' in feature:
                feature_name = 'averages'

            for feature_index, (host_name, days) in enumerate(hosts.items()):
                if feature_index == 0:
                    try:
                        combined_sorted_stats[f'daily_{feature_name}']['host_name'].append('')
                        for day in days.keys():
                            combined_sorted_stats[f'daily_{feature_name}']['Day' + str(day)].append('')
                        combined_sorted_stats[f'daily_{feature_name}']['host_name'].append(f'{host_type}_{feature}')
                        for day in days.keys():
                            (combined_sorted_stats[f'daily_{feature_name}']['Day' + str(day)].
                             append('Day' + str(day)))
                    except KeyError:
                        combined_sorted_stats[f'daily_{feature_name}'] = {f'host_name': [f'{host_type}_{feature}']}
                        for day in days.keys():
                            combined_sorted_stats[f'daily_{feature_name}']['Day' + str(day)] = ['Day' + str(day)]

                combined_sorted_stats[f'daily_{feature_name}']['host_name'].append(host_name)
                for day_number, counter in days.items():
                    combined_sorted_stats[f'daily_{feature_name}']['Day' + str(day_number)].append(counter)

    try:
        xlsxs.write_xlsx(combined_sorted_stats, file_path=summary_path)
    except FileNotFoundError:
        directory_path = filesystem.get_file_directory(summary_path)
        print_api(f'Directory does not exist, creating it: {directory_path}')
        filesystem.create_directory(directory_path)
        xlsxs.write_xlsx(combined_sorted_stats, file_path=summary_path)

    return

import os
import datetime
import json
from typing import Union, Literal
import argparse

from .statistic_analyzer_helper import analyzer_helper, moving_average_helper
from .. import filesystem, domains, datetimes, urls
from ..basics import dicts
from ..file_io import tomls, xlsxs, jsons, csvs
from ..wrappers.loggingw import reading
from ..print_api import print_api


STATISTICS_FILE_NAME: str = 'statistics.csv'


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
    log_file_path_pattern: str = f"{config['statistic_files_path']}{os.sep}statistics.csv"
    statistics_content: list = reading.get_all_log_files_into_list(
        log_file_path=log_file_path_pattern,
        log_type='csv'
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
        'domain': analyzer_helper.create_empty_features_dict(),
        'subdomain': analyzer_helper.create_empty_features_dict(),
        'url_no_parameters': analyzer_helper.create_empty_features_dict()
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
            last_day_number = analyzer_helper.get_the_last_day_number(statistics_content, break_after_lines)

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
        analyzer_helper.add_to_count_to_daily_stats(
            daily_stats, day_number, last_day_number, 'domain', 'total_count', main_domain)
        analyzer_helper.add_to_count_to_daily_stats(
            daily_stats, day_number, last_day_number, 'subdomain', 'total_count', subdomain)
        analyzer_helper.add_to_count_to_daily_stats(
            daily_stats, day_number, last_day_number, 'url_no_parameters', 'total_count', url_no_parameters)

        # Handle line if it has error.
        if line['error'] != '':
            analyzer_helper.add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'domain', 'error_count', main_domain)
            analyzer_helper.add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'subdomain', 'error_count', subdomain)
            analyzer_helper.add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'url_no_parameters', 'error_count', url_no_parameters)
        else:
            analyzer_helper.add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'domain', 'normal_count', main_domain)
            analyzer_helper.add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'subdomain', 'normal_count', subdomain)
            analyzer_helper.add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'url_no_parameters', 'normal_count', url_no_parameters)

        if request_size == 0:
            analyzer_helper.add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'domain', 'request_0_byte_count',
                main_domain)
            analyzer_helper.add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'subdomain', 'request_0_byte_count',
                subdomain)
            analyzer_helper.add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'url_no_parameters', 'request_0_byte_count',
                url_no_parameters)

        if response_size == 0:
            analyzer_helper.add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'domain', 'response_0_byte_count',
                main_domain)
            analyzer_helper.add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'subdomain', 'response_0_byte_count',
                subdomain)
            analyzer_helper.add_to_count_to_daily_stats(
                daily_stats, day_number, last_day_number, 'url_no_parameters', 'response_0_byte_count',
                url_no_parameters)

        if request_size is not None and response_size is not None:
            analyzer_helper.add_to_list_to_daily_stats(
                daily_stats, day_number, last_day_number, 'domain', 'request_sizes_list', main_domain, request_size)
            analyzer_helper.add_to_list_to_daily_stats(
                daily_stats, day_number, last_day_number, 'subdomain', 'request_sizes_list', subdomain, request_size)
            analyzer_helper.add_to_list_to_daily_stats(
                daily_stats, day_number, last_day_number, 'url_no_parameters', 'request_sizes_list', url_no_parameters,
                request_size)

            analyzer_helper.add_to_list_to_daily_stats(
                daily_stats, day_number, last_day_number, 'domain', 'response_sizes_list', main_domain, response_size)
            analyzer_helper.add_to_list_to_daily_stats(
                daily_stats, day_number, last_day_number, 'subdomain', 'response_sizes_list', subdomain, response_size)
            analyzer_helper.add_to_list_to_daily_stats(
                daily_stats, day_number, last_day_number, 'url_no_parameters', 'response_sizes_list', url_no_parameters,
                response_size)

        if request_size != 0 and request_size is not None:
            analyzer_helper.add_to_list_to_daily_stats(
                daily_stats, day_number, last_day_number, 'domain', 'request_sizes_no_0_bytes_list',
                main_domain, request_size)
            analyzer_helper.add_to_list_to_daily_stats(
                daily_stats, day_number, last_day_number, 'subdomain', 'request_sizes_no_0_bytes_list',
                subdomain, request_size)
            analyzer_helper.add_to_list_to_daily_stats(
                daily_stats, day_number, last_day_number, 'url_no_parameters', 'request_sizes_no_0_bytes_list',
                url_no_parameters, request_size)

        if response_size != 0 and response_size is not None:
            analyzer_helper.add_to_list_to_daily_stats(
                daily_stats, day_number, last_day_number, 'domain', 'response_sizes_no_0_bytes_list',
                main_domain, response_size)
            analyzer_helper.add_to_list_to_daily_stats(
                daily_stats, day_number, last_day_number, 'subdomain', 'response_sizes_no_0_bytes_list',
                subdomain, response_size)
            analyzer_helper.add_to_list_to_daily_stats(
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
                    analyzer_helper.add_to_average_to_daily_stats(
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


# ======================================================================================================================


def deviation_calculator_by_moving_average(
        statistics_file_directory: str = None,
        statistics_content: dict = None,
        by_type: Literal['host', 'url'] = 'url',
        moving_average_window_days: int = 5,
        top_bottom_deviation_percentage: float = 0.25,
        get_deviation_for_last_day_only: bool = False,
        summary: bool = False,
        output_file_path: str = None,
        output_file_type: Literal['json', 'csv'] = 'json',
        convert_sizes_lists_and_ma_data_to_string: bool = False,
        skip_total_count_less_than: int = None
) -> Union[list, None]:
    """
    This function is the main function for the moving average calculator.

    :param statistics_file_directory: string, can be either providing the directory where 'statistics.csv' file resides
        or None. If None, the 'statistics_content' must be provided.
        The directory where 'statistics.csv' file resides.
        Also, all the rotated files like: statistics_2021-01-01.csv, statistics_2021-01-02.csv, etc.
        These will be analyzed in the order of the date in the file name.
    :param statistics_content: dict, if specified, this will be used instead of reading the files from the directory.
        The dict should be a result of the 'atomicshop.mitm.statistic_analyzer_helper.moving_average_helper.get_all_files_content'.
    :param by_type: string, 'host' or 'url'. The type of the deviation calculation.
        'host' will calculate the deviation by the host name. Example: maps.google.com, yahoo.com, etc.
        'url' will calculate the deviation by the URL. Example: maps.google.com/maps, yahoo.com/news, etc.
    :param moving_average_window_days: integer, the moving average window days.
    :param top_bottom_deviation_percentage: float, the top bottom deviation percentage. Example: 0.1 for 10%.
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
    :param summary: bool, if True, Only the summary will be generated without all the numbers that were used
        to calculate the averages and the moving average data.
    :param output_file_path: string, if None, no file will be written.
    :param output_file_type: string, the type of the output file. 'json' or 'csv'.
    :param convert_sizes_lists_and_ma_data_to_string: bool, if True, the 'request_sizes', 'response_sizes' and 'ma_data'
        will be converted to string. This is useful when writing to files, so the view will be more readable.
    :param skip_total_count_less_than: integer, if specified, the deviation calculation will be skipped
        if the total count is less than this number.
        This means that if we have moving average window of 7 days, on the 8th day, the deviation will be calculated
        only if the total count of the checked type
        (request average size, response average, request count, response count)
        is greater or equal to this number.
    -----------------------------
    :return: the deviation list of dicts.

    Example:
    import sys
    from atomicshop.mitm import statistic_analyzer


    def main():
        return statistic_analyzer.moving_average_calculator_main(
            statistics_file_path='statistics.csv',
            moving_average_window_days=7,
            top_bottom_deviation_percentage=0.1,
            output_json_file='C:\\output\\deviation_list.json'
        )


    if __name__ == '__main__':
        sys.exit(main())
    """

    def convert_data_value_to_string(value_key: str, list_index: int) -> None:
        deviation_list[list_index]['data'][value_key] = json.dumps(deviation_list[list_index]['data'][value_key])

    def convert_value_to_string(value_key: str, list_index: int) -> None:
        if value_key in deviation_list[list_index]:
            deviation_list[list_index][value_key] = json.dumps(deviation_list[list_index][value_key])

    if not statistics_file_directory and not statistics_content:
        raise ValueError('Either [statistics_file_directory] or [statistics_content] must be provided.')
    if statistics_file_directory and statistics_content:
        raise ValueError('Either [statistics_file_directory] or [statistics_content] must be provided, not both.')

    if output_file_type not in ['json', 'csv']:
        raise ValueError(f'output_file_type must be "json" or "csv", not [{output_file_type}]')

    if by_type not in ['host', 'url']:
        raise ValueError(f'by_type must be "host" or "url", not [{by_type}]')

    if statistics_file_directory:
        statistics_file_path: str | None = f'{statistics_file_directory}{os.sep}{STATISTICS_FILE_NAME}'
    else:
        statistics_file_path: str | None = None

    deviation_list = moving_average_helper.calculate_moving_average(
        statistics_file_path,
        statistics_content,
        by_type,
        moving_average_window_days,
        top_bottom_deviation_percentage,
        get_deviation_for_last_day_only,
        skip_total_count_less_than
    )

    if deviation_list:
        if convert_sizes_lists_and_ma_data_to_string:
            for deviation_list_index, deviation in enumerate(deviation_list):
                convert_data_value_to_string('request_sizes', deviation_list_index)
                convert_data_value_to_string('response_sizes', deviation_list_index)
                convert_value_to_string('ma_data', deviation_list_index)

        if summary:
            for deviation in deviation_list:
                _ = deviation.pop('check_type')
                _ = deviation.pop('percentage')
                _ = deviation.pop('ma_value_checked')
                _ = deviation.pop('deviation_type')
                _ = deviation.pop('data')
                _ = deviation.pop('ma_data')

        if output_file_path:
            print_api(f'Deviation Found, saving to file: {output_file_path}', color='blue')

            if output_file_type == 'csv':
                csvs.write_list_to_csv(deviation_list, output_file_path)
            elif output_file_type == 'json':
                jsons.write_json_file(deviation_list, output_file_path, use_default_indent=True)

        return deviation_list

    return []


def deviation_calculator_by_moving_average_main():
    def parse_args():
        description_full: str = (
            f'Description: Calculate deviation by moving average.')

        parser = argparse.ArgumentParser(
            description=description_full)

        parser.add_argument(
            '-d', '--directory', type=str, required=True,
            help='Provide full path to directory with statistics.csv files.')
        parser.add_argument(
            '-of', '--output_file', type=str, required=True, help='Provide full path to output file.')
        parser.add_argument(
            '-ot', '--output_type', type=str, required=True, help='Provide output type: [json] or [csv].')
        parser.add_argument(
            '-by', '--by_type', type=str, required=True, help='Calculate by [host] or [url].')
        parser.add_argument(
            '-f', '--full_details', action='store_true', required=False,
            help='(OPTIONAL) Output full processing details instead of summary.')
        parser.add_argument(
            '-w', '--window', type=int, required=True, help='Moving average window in days.')
        parser.add_argument(
            '-p', '--percentage', type=float, required=True,
            help='Percentage of deviation from moving average. Example: 0.1 for 10%%.')
        parser.add_argument(
            '-slt', '--skip_total_count_less_than', type=int, required=False,
            help='An integer to skip the deviation calculation if the total count is less than this number.')

        return parser.parse_args()

    args = parse_args()

    if args.output_type == 'csv' and args.full_details:
        print_api("Full details output is not supported for csv files.", color='red')
        return 1

    if not os.path.isdir(args.directory):
        print_api(f"Directory does not exist: {args.directory}", color='red')
        return 1

    if not filesystem.get_paths_from_directory(
            directory_path=args.directory, get_file=True, simple_list=True, file_name_check_pattern='*statistics*.csv'):
        print_api(f"No statistics files found in: {args.directory}", color='red')
        return 1

    if args.full_details:
        summary = False
        convert_sizes_lists_and_ma_data_to_string = True
    else:
        summary = True
        convert_sizes_lists_and_ma_data_to_string = False

    _ = deviation_calculator_by_moving_average(
        statistics_file_directory=args.directory,
        by_type=args.by_type,
        moving_average_window_days=args.window,
        top_bottom_deviation_percentage=args.percentage,
        summary=summary,
        output_file_path=args.output_file,
        output_file_type=args.output_type,
        convert_sizes_lists_and_ma_data_to_string=convert_sizes_lists_and_ma_data_to_string,
        skip_total_count_less_than=args.skip_total_count_less_than
    )

    return 0

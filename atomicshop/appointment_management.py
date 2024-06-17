import os
import datetime

from .print_api import print_api
from .basics.lists import remove_duplicates
from .datetimes import convert_single_digit_to_zero_padded, create_date_range_for_year, \
    create_date_range_for_year_month
from .file_io import csvs


class AppointmentManager:
    def __init__(self, working_directory: str, skip_days: int = 0):
        self.working_directory: str = working_directory

        self.latest_date_to_check_filename: str = 'latest_date.csv'
        self.latest_date_to_check_filepath: str = \
            self.working_directory + os.sep + self.latest_date_to_check_filename

        # After this time we don't need available appointments.
        self.latest_date_to_check = None
        # The earliest date to check is now.
        self.earliest_date_to_check = datetime.datetime.now()

        # Read the CSV file with latest date to check.
        self.read_latest_date_csv()

        # If 'skip_days' was specified.
        if skip_days != 0:
            # We'll add the number of days specified to current time, and now it will be the earliest time to check.
            self.earliest_date_to_check = self.earliest_date_to_check + datetime.timedelta(days=skip_days)
            # Remove the time completely, so it will check from the day beginning.
            self.earliest_date_to_check = self.earliest_date_to_check.replace(
                hour=00, minute=00, second=00, microsecond=0)

        self.blacklist_engine = BlacklistEngine(self.working_directory)
        self.blacklist_dates = list(self.blacklist_engine.blacklist_dates_list)

    def read_latest_date_csv(self):
        try:
            # Read the csv to list of dicts.
            csv_list, _ = csvs.read_csv_to_list_of_dicts_by_header(
                file_path=self.latest_date_to_check_filepath, raise_exception=True)
            # It has only 1 line, so get it to dict.
            latest_date_dict = csv_list[0]

            # Convert month and day to zero padded 2 digit.
            latest_date_dict['month'] = convert_single_digit_to_zero_padded(latest_date_dict['month'])
            latest_date_dict['day'] = convert_single_digit_to_zero_padded(latest_date_dict['day'])

            # Make a datetime string and convert it to datetime object.
            latest_date_string = f"{latest_date_dict['day']}.{latest_date_dict['month']}." \
                                 f"{latest_date_dict['year']} {latest_date_dict['time']}"
            self.latest_date_to_check = datetime.datetime.strptime(latest_date_string, "%d.%m.%Y %H:%M")
        # If the file wasn't found we will not use the latest time to check at all.
        except FileNotFoundError:
            print_api("Assuming you don't need this functionality", color='yellow')
            pass

    def find_earliest_date(self, date_list: list, **kwargs):
        date_list.sort()
        print_api(f"Dates to check: {date_list}", **kwargs)
        for single_date in date_list:
            # Check if current date iteration is not blacklisted and between earliest and latest dates.
            if single_date not in self.blacklist_dates and \
                    self.earliest_date_to_check.date() <= single_date <= self.latest_date_to_check.date():
                return single_date

        return None


class BlacklistEngine:
    """
    BlacklistEngine class is responsible for 'appointments_blacklist.csv' file and its processing.
    Rules:
        * Except by day only:
            If you specify only the day (example: day='16', month='', year=''), each 16th of each month will be skipped.
        * Except by month only:
            If you specify only the month (example: day='', month='02', year=''), the whole february of every year
            will be skipped.
        * Except by year only:
            If you specify only the year (example: day='', month='', year='2022'), the whole 2022 year will be skipped.
        * Except by day and month only:
            If you specify only the day and month (example: day='16', month='02', year=''), each 16th of february
            every year will be skipped.
        * Except by month and year:
            If you specify only the month and year (example: day='', month='02', year='2022'), the whole february
            2022 will be skipped.
        * Except by full date:
            If you specify the day, month and year (example: day='16', month='02', year='2022'), only the 16th of
            february 2022 will be skipped.
    """
    
    def __init__(self, working_directory: str):
        self.blacklist_dates_filename: str = 'appointments_blacklist.csv'
        self.blacklist_dates_filepath: str = working_directory + os.sep + self.blacklist_dates_filename
        self.blacklist_dates_list: list = list()

        # Read the CSV file.
        self.read_blacklist_csv()

    def read_blacklist_csv(self) -> None:
        try:
            # Read the csv to list of dicts.
            csv_list, _ = csvs.read_csv_to_list_of_dicts_by_header(
                file_path=self.blacklist_dates_filepath, raise_exception=True)

            daterange = None
            # Iterate through all the rows.
            for row in csv_list:
                if row['day'] != '' and row['month'] == '' and row['year'] != '':
                    message = f'You specified "day" and "year", but not "month" ' \
                              f'in "{self.blacklist_dates_filename}", this is not allowed:\n' \
                              f'{row}'
                    print_api(message, message_type_error=True, color='red', exit_on_error=True)
                elif row['day'] == '' and row['month'] == '' and row['year'] == '':
                    continue

                # If there's no 'day' and 'month' specified, add thw row as is.
                if row['year'] and not row['month'] and not row['day']:
                    # Generate datetime range list.
                    daterange = create_date_range_for_year(int(row['year']), from_today_for_same_year=True)
                # If there's no 'day' specified, add thw row as is.
                elif row['year'] and row['month'] and not row['day']:
                    # Generate datetime range list.
                    daterange = create_date_range_for_year_month(
                        int(row['year']), int(row['month']), from_today_for_same_month=True)
                # If all the elements specified, convert to datetime.
                elif row['year'] and row['month'] and row['day']:
                    daterange = [datetime.datetime(int(row['year']), int(row['month']), int(row['day'])).date()]

                # If 'daterange' was created.
                if daterange:
                    # We'll add it to the list.
                    self.blacklist_dates_list += daterange
            # For loop for CSV row cycles ends here

            self.blacklist_dates_list = remove_duplicates(self.blacklist_dates_list)
            self.blacklist_dates_list.sort()

        # If the file wasn't found we will not use the latest time to check at all.
        except FileNotFoundError:
            print_api("Assuming you don't need this functionality", color='yellow')
            pass

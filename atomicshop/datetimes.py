import datetime
from datetime import timedelta
import time
import random
import re
from typing import Union


class MonthToNumber:
    ENGLISH_SHORT: dict = {
        'Jan': '01',
        'Feb': '02',
        'Mar': '03',
        'Apr': '04',
        'May': '05',
        'Jun': '06',
        'Jul': '07',
        'Aug': '08',
        'Sep': '09',
        'Oct': '10',
        'Nov': '11',
        'Dec': '12'}
    ENGLISH_LONG: dict = {
        'January': '01',
        'February': '02',
        'March': '03',
        'April': '04',
        'May': '05',
        'June': '06',
        'July': '07',
        'August': '08',
        'September': '09',
        'October': '10',
        'November': '11',
        'December': '12'}
    HEBREW: dict = {
        'ינואר': '01',
        'פברואר': '02',
        'מרץ': '03',
        'אפריל': '04',
        'מאי': '05',
        'יוני': '06',
        'יולי': '07',
        'אוגוסט': '08',
        'ספטמבר': '09',
        'אוקטובר': '10',
        'נובמבר': '11',
        'דצמבר': '12'}


# Mapping of datetime format specifiers to regex patterns
DATE_TIME_STRING_FORMAT_SPECIFIERS_TO_REGEX: dict = {
    '%Y': r'\d{4}',   # Year with century
    '%m': r'\d{2}',   # Month as a zero-padded decimal number
    '%d': r'\d{2}',   # Day of the month as a zero-padded decimal number
    '%H': r'\d{2}',   # Hour (24-hour clock) as a zero-padded decimal number
    '%I': r'\d{2}',   # Hour (12-hour clock) as a zero-padded decimal number
    '%M': r'\d{2}',   # Minute as a zero-padded decimal number
    '%S': r'\d{2}',   # Second as a zero-padded decimal number
    '%f': r'\d{6}',   # Microsecond as a decimal number, zero-padded on the left
    '%j': r'\d{3}',   # Day of the year as a zero-padded decimal number
    '%U': r'\d{2}',   # Week number of the year (Sunday as the first day of the week)
    '%W': r'\d{2}',   # Week number of the year (Monday as the first day of the week)
    '%w': r'\d',      # Weekday as a decimal number (0 = Sunday, 6 = Saturday)
    '%y': r'\d{2}',   # Year without century
    '%p': r'(AM|PM)',   # AM or PM
    '%z': r'[+-]\d{4}',  # UTC offset in the form ±HHMM
    '%Z': r'[A-Z]+',     # Time zone name
    '%%': r'%'           # Literal '%'
}


def get_datetime_from_complex_string_by_pattern(
        complex_string: str,
        date_pattern: str
) -> tuple[
    Union[datetime.datetime, None],
    Union[str, None],
    Union[float, None]
]:
    """
    Function will get datetime object from a complex string by pattern.

    :param complex_string: string that contains date and time.
    :param date_pattern: pattern that will be used to extract date and time from the string.
    :return: tuple(datetime object, date string, timestamp float)
    """

    # Convert the date pattern to regex pattern
    regex_pattern = re.sub(r'%[a-zA-Z]', r'\\d+', date_pattern)

    # Find the date part in the file name using the regex pattern
    date_str = re.search(regex_pattern, complex_string)

    if date_str:
        # Convert the date string to a datetime object based on the given pattern
        date_obj = datetime.datetime.strptime(date_str.group(), date_pattern)
        date_timestamp = date_obj.timestamp()
        return date_obj, date_str.group(), date_timestamp
    else:
        return None, None, None


def datetime_format_to_regex(format_str: str) -> str:
    """
    Convert a datetime format string to a regex pattern.

    :param format_str: The datetime format string to convert.
    :return: The regex pattern that matches the format string.

    Example:
    datetime_format_to_regex("%Y-%m-%d")

    Output:
    '^\\d{4}-\\d{2}-\\d{2}$'
    """

    # Escape all non-format characters
    escaped_format_str = re.escape(format_str)

    # Replace escaped format specifiers with their regex equivalents
    for specifier, regex in DATE_TIME_STRING_FORMAT_SPECIFIERS_TO_REGEX.items():
        escaped_format_str = escaped_format_str.replace(re.escape(specifier), regex)

    # Return the full regex pattern with start and end anchors
    return f"^{escaped_format_str}$"


def extract_datetime_format_from_string(complex_string: str) -> Union[str, None]:
    """
    Extract the datetime format from the suffix used in TimedRotatingFileHandler.

    Args:
    - suffix: The suffix string from the handler.

    Returns:
    - The datetime format string, or None if it cannot be determined.
    """
    # Regular expression to match datetime format components in the suffix
    datetime_format_regex = r"%[a-zA-Z]"
    matches = re.findall(datetime_format_regex, complex_string)
    if matches:
        return "".join(matches)
    return None


def convert_single_digit_to_zero_padded(string: str):
    """
    Function will check if string is a single character digit and will add zero in front of it.

    :param string:
    :return:
    """

    if len(string) == 1:
        string = '0' + string

    return string


def create_datetime_by_ymd(year, month, day):
    """
    Function will create datetime object from year, month and day.
    """

    # Make sure passed arguments are integers.
    if not isinstance(year, int):
        year = int(year)
    if not isinstance(month, int):
        month = int(month)
    if not isinstance(day, int):
        day = int(day)

    return datetime.datetime(year, month, day)


def get_date_only_from_datetime(datetime_object):
    return datetime_object.date()


def get_time_only_from_datetime(datetime_object):
    return datetime_object.time()


def get_last_date_of_month(year: int, month: int):
    # There is no 13th month. 'last_date' is the last day of the month.
    if month == 12:
        last_date = datetime.datetime(year, month, 31).date()
    else:
        # Get next month (year, month + 1, 1) and subtract from it 1 day to get the last day of current month.
        last_date = datetime.datetime(year, month + 1, 1) + datetime.timedelta(days=-1)
        last_date = last_date.date()

    return last_date


def create_date_range(first_date, last_date) -> list:
    """
    Create list of datetime objects from 'first_date' till 'last_date' including both.

    :param first_date:
    :param last_date:
    :return:
    """

    # first_date = datetime.datetime(2022, 11, 19).date()
    # last_date = datetime.datetime(2022, 12, 31).date()
    # first_date = first_date.date()
    # last_date = last_date.date()
    daterange = [first_date + datetime.timedelta(days=x) for x in range(0, (last_date-first_date).days+1)]
    return daterange


def create_date_range_for_year(year: int, from_today: bool = False, from_today_for_same_year: bool = False):
    first_date = None
    today_date = None

    # if 'from_today' or 'from_today_for_same_year' wes set to 'True'.
    if from_today or from_today_for_same_year:
        # Get today date in 'date()' format only.
        today_date = datetime.datetime.today().date()

        # If today's year is later than specified 'year'.
        if year < today_date.year:
            return None

    # If 'from_today' was specified, we'll create date range from today until end of specified year.
    if from_today:
        # If today's year is specified 'year' or earlier.
        if year >= today_date.year:
            # 'first_date' will be today, we don't need to generate range for the whole year.
            first_date = today_date
    # If 'from_today_for_same_year' was specified, we'll create date range from today until end of current year.
    elif from_today_for_same_year and year == today_date.year:
        # 'first_date' will be today, we don't need to generate range for the whole year.
        first_date = today_date
    # If today's year is not specified 'year'.
    else:
        # 'first_date' will be from beginning of the specified 'year'.
        first_date = datetime.datetime(year, 1, 1)

    # 'last_date' is the last day of the year.
    last_date = datetime.datetime(year, 12, 31).date()

    return create_date_range(first_date, last_date)


def create_date_range_for_year_month(
        year: int, month: int, from_today: bool = False, from_today_for_same_month: bool = False):
    first_date = None
    today_date = None

    # if 'from_today' or 'from_today_for_same_year' wes set to 'True'.
    if from_today or from_today_for_same_month:
        # Get today date in 'date()' format only.
        today_date = datetime.datetime.today().date()

        # If today's year is later than specified 'year'.
        if year < today_date.year:
            return None
        # If today's month is later than specified 'month'.
        if month < today_date.month:
            return None

    # If 'from_today' was specified, we'll create date range from today until end of specified year+month.
    if from_today:
        # If today's year and month is specified 'year' and month or earlier.
        if year >= today_date.year and month >= today_date.month:
            # 'first_date' will be today, we don't need to generate range for the whole year.
            first_date = today_date
    # If 'from_today_for_same_year' was specified, we'll create date range from today until end of current year.
    elif from_today_for_same_month and year == today_date.year and month == today_date.month:
        # 'first_date' will be today, we don't need to generate range for the whole year.
        first_date = today_date
    # If none of 'from_today' switches were specified or 'first_date' weren't assigned in 'from_today_for_same_month'.
    else:
        first_date = datetime.datetime(year, month, 1).date()

    last_date = get_last_date_of_month(year, month)

    return create_date_range(first_date, last_date)


def get_difference_between_dates_in_days(first_datetime, reference_datetime) -> int:
    """
    Get the difference between two dates in days.
    The first day is '0'.

    :param first_datetime: datetime.datetime object.
    :param reference_datetime: datetime.datetime object.

    :return: integer, the difference between the two dates in days.
    """

    # Get the difference between the two dates.
    difference = reference_datetime - first_datetime

    # Get the difference in days.
    return difference.days


def get_difference_between_dates_in_hours(first_datetime, reference_datetime) -> int:
    """
    Get the difference between two dates in hours.
    The first hour is '0'.

    :param first_datetime: datetime.datetime object.
    :param reference_datetime: datetime.datetime object.

    :return: integer, the difference between the two dates in hours.
    """

    # Get the difference between the two dates.
    difference = first_datetime - reference_datetime

    # Get the difference in hours.
    return difference.days * 24 + difference.seconds // (60 * 60)


def get_seconds_random(minimum_seconds, maximum_seconds):
    return random.randint(minimum_seconds, maximum_seconds)


def get_milliseconds_random(minimum_float, maximum_float):
    """
    'time.sleep()' works in seconds. 'time.sleep(1)' will sleep 1 second.
    If you want to 'sleep()' for milliseconds and lower, you need to use 'floats':
        'time.sleep(0.1)' will sleep 100 milliseconds.
    So, providing float numbers you will specify also milliseconds.

    Example:
        get_milliseconds_random(0.01, 0.4)
    Result:
        It will return between 10ms to 400ms.

    :param minimum_float:
    :param maximum_float:
    :return:
    """

    random.uniform(minimum_float, maximum_float)


class TimeFormats:
    def __init__(self):
        self.time_format = None

    def get_current_formatted_time_http(self):
        # Example: 'Tue, 08 Nov 2022 14:23: 00 GMT'
        self.time_format = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
        return self.time_format

    def get_current_formatted_time_protobuf(self):
        # Example: '2023-02-08T13:49:50.247686031Z'
        self.time_format = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f000Z")
        return self.time_format

    def get_current_formatted_time_unix_epoch(self):
        # '.timestamp()' or 'time.time()' returns object as 'float' with a point: 1676916005.482013
        # To get rid of it we're converting it to int.
        # Also, timestamp returned is 10 digit epoch time float. Unix epoch time is 13 digit integer. So, we'll
        # multiply the result by 1000m then convert it to integer to drop the numbers after point.

        # return int(datetime.datetime.now().timestamp()*1000)

        self.time_format = int(time.time()*1000)
        return self.time_format

    def get_current_formatted_time_filename_stamp(self, include_milliseconds: bool = True):
        # Example: '20230208-134950'
        # Example with 'include_milliseconds=True': '20230208-134950-247686'

        if include_milliseconds:
            self.time_format = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        else:
            self.time_format = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

        return self.time_format


class TimeConverter:
    def __init__(self):
        self.time_converted = None

    def convert_epoch_unix_to_datetime(self, unix_epoch_timestamp, no_milliseconds: bool = False):
        """
        Unix epoch time is 13 digit integer / float. Regular python epoch is 10.

        :param unix_epoch_timestamp: int / float.
        :param no_milliseconds: bool
        :return: datetime
        """

        # Converting unix 13 digit epoch timestamp.
        # 'fromtimestamp()' should get 10 digit epoch time, which is standard inside python.
        # Putting 13 digit unix epoch time will result in
        # OSError: [Errno 22] Invalid argument
        # so, we'll divide it by 1000.
        python_timestamp = unix_epoch_timestamp / 1000

        # If you don't want milliseconds, you can convert the number to integer.
        if no_milliseconds:
            python_timestamp = int(python_timestamp)

        self.time_converted = datetime.datetime.fromtimestamp(python_timestamp)
        return self.time_converted

    def convert_epoch_python_to_datetime(self, python_epoch_timestamp, no_milliseconds: bool = False):
        """
        Regular python epoch time is 10 digit integer / float.

        :param python_epoch_timestamp: int / float.
        :param no_milliseconds: bool
        :return: datetime
        """

        # If you don't want milliseconds, you can convert the number to integer.
        if no_milliseconds:
            python_epoch_timestamp = int(python_epoch_timestamp)

        self.time_converted = datetime.datetime.fromtimestamp(python_epoch_timestamp)
        return self.time_converted

    def convert_datetime_to_epoch_python(self, datetime_object, no_milliseconds: bool = False):
        # '.timestamp()' returns 10 digit object as 'float' with a point: 1676916005.482013
        # To get rid of it we're converting it to int.

        python_epoch_timestamp = datetime_object.timestamp()

        if no_milliseconds:
            python_epoch_timestamp = int(python_epoch_timestamp)

        self.time_converted = python_epoch_timestamp
        return self.time_converted

    def convert_datetime_to_epoch_unix(self, datetime_object, no_milliseconds: bool = False):
        # '.timestamp()' returns 10 digit object as 'float' with a point: 1676916005.482013
        # To get rid of it we're converting it to int.
        # Also, timestamp returned is 10 digit epoch time float. Unix epoch time is 13 digit integer. So, we'll
        # multiply the result by 1000m then convert it to integer to drop the numbers after point.

        unix_epoch_timestamp = datetime_object.timestamp() * 1000

        if no_milliseconds:
            unix_epoch_timestamp = int(unix_epoch_timestamp)

        self.time_converted = unix_epoch_timestamp
        return self.time_converted


def convert_delta_string_to_seconds(interval):
    """
    The function gets interval in integer / float / tuple. If it's a 'tuple' converts it to float.
    If it's 'int' or 'float' return as is.
    Other types raise an exception.

    Usage:
        # Convert 1 day to seconds.
        convert_delta_string_to_seconds('days', 1)
        # Convert 2 minutes to seconds.
        convert_delta_string_to_seconds('minutes', 2)

    :param interval: integer, float or tuple.
        Integer or float: the interval in seconds between function executions.
        Tuple: contains two variables. The first one is a string that represents the timedelta
            (eg: 'seconds', 'minutes') and the second variable represents the amount.
    :return: float, seconds if the input is tuple. If it's 'int' or 'float' return as is.
    """

    # If 'interval' is 'int' type or 'float'.
    if isinstance(interval, int) or isinstance(interval, float):
        # Nothing needs to be done.
        return interval
    # If 'interval' is 'tuple' type.
    elif isinstance(interval, tuple):
        # Get both values from interval. The first is 'delta' date string (eg: 'seconds', 'minutes'), the second is
        # amount of type integer.
        delta_string, amount = interval

        # Define empty seconds float.
        seconds_float: float = float()

        # Convert the delta string date and amount to seconds.
        if delta_string == 'seconds':
            seconds_float = timedelta(seconds=amount).total_seconds()
        elif delta_string == 'minutes':
            seconds_float = timedelta(minutes=amount).total_seconds()
        elif delta_string == 'hours':
            seconds_float = timedelta(hours=amount).total_seconds()
        elif delta_string == 'days':
            seconds_float = timedelta(days=amount).total_seconds()

        return seconds_float
    # If the 'interval' type is not 'int', 'float' or 'tuple'.
    else:
        raise TypeError('"interval" is not "int", "float", nor "tuple".')

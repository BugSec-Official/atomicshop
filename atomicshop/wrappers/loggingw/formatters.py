import logging
import time

from . import consts


# Log formatter, means how the log will look inside the file
# Format for specific object: %(levelname)s
# Format with adding spaces after the object with maximum of 10 characters: %(levelname)-10s
# Format with adding spaces before the object with maximum of 10 characters: %(levelname)10s

# ".40" truncating the string to only 40 characters. Example: %(message).250s


class NanosecondsFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None, style='%', use_nanoseconds=False):
        super().__init__(fmt, datefmt, style)
        self.use_nanoseconds = use_nanoseconds

    def formatTime(self, record, datefmt=None):
        ct = self.converter(record.created)

        if datefmt:
            # Remove unsupported %f from datefmt if present
            if '%f' in datefmt:
                datefmt = datefmt.replace('%f', '')
                self.use_nanoseconds = True
        else:
            # Default time format if datefmt is not provided
            datefmt = '%Y-%m-%d %H:%M:%S'

        s = time.strftime(datefmt, ct)

        if self.use_nanoseconds:
            # Calculate nanoseconds from the fractional part of the timestamp
            nanoseconds = f'{record.created:.9f}'.split('.')[1]
            # Return the formatted string with nanoseconds appended
            return f'{s}.{nanoseconds}'
        else:
            return s


class FormatterProcessor:
    """
    Class to process the formatter.
    """
    def __init__(self, formatter: str):
        """
        :param formatter: Formatter to process.
        """
        self.formatter: str = formatter

        self.style: dict = dict()
        self.list_of_elements: list = list()

    def get_style(self) -> dict:
        """
        Function to get the style from the formatter.
        :return: Style from the formatter.
        """

        if '%' in self.formatter:
            result = {
                'style': '%',
                'open': '(',
                'close': ')'
            }
            return result
        elif '{' in self.formatter:
            result = {
                'style': '{',
                'open': '{',
                'close': '}'
            }

            return result

    def get_list_of_elements(self) -> list:
        """
        Function to process the formatter parts.
        :return: list, of elements from formatter.
        """

        # If the style is not defined, get it.
        if not self.style:
            self.style = self.get_style()

        formatter_parts = self.formatter.split(self.style['style'])

        # Removing the first element, if it is empty.
        if self.style['open'] not in formatter_parts[0]:
            del formatter_parts[0]

        header_list: list = list()
        for formatter_part in formatter_parts:
            # Cut everything before and after parentheses included.
            header_part = formatter_part.split(self.style['open'])[1]
            header_part = header_part.split(self.style['close'])[0]
            header_list.append(header_part)

        return header_list

    def get_header_dict(self) -> dict:
        """
        Function to get the header from the formatter.
        :return: Header from the formatter.
        """

        # If the list of elements is not defined, get it.
        if not self.list_of_elements:
            # To get list of elements, we need to get the style first. If the style is not defined, get it.
            if not self.style:
                self.style = self.get_style()

            self.list_of_elements = self.get_list_of_elements()

        # Iterate through all the elements and get the header list.
        header_dict: dict = dict()
        for element in self.list_of_elements:
            header_dict.update({element: consts.FORMAT_ELEMENT_TO_HEADER[element]})

        return header_dict


def get_logging_formatter_from_string(
        formatter: str,
        style=None,
        datefmt=None,
        use_nanoseconds: bool = False
) -> logging.Formatter:
    """
    Function to get the logging formatter from the string.

    :param formatter: string formatter to convert to 'logging.Formatter'.
    :param style: string, style of the formatter. Default is None.
        None: will try to detect the style.
        '%': will use the '%' style.
        '{': will use the '{' style.
    :param datefmt: string, date format of 'asctime' element. Default is None.
        We use custom formatter that can process the date format with nanoseconds:
        '%Y-%m-%d %H:%M:%S.%f' -> '2021-01-01 00:00:00.000000000'
    :param use_nanoseconds: bool, if set to True, the formatter will use nanoseconds instead of milliseconds.
        This will print 'asctime' in the following format: '2021-01-01 00:00:00.000000000', instead of
        '2021-01-01 00:00:00.000'.

    :return: logging.Formatter, formatter.
    """

    # If the style is not defined, get it.
    if not style:
        style = FormatterProcessor(formatter).get_style()['style']

    # Create the logging formatter.
    if use_nanoseconds or '%f' in datefmt:
        return NanosecondsFormatter(formatter, style=style, datefmt=datefmt, use_nanoseconds=use_nanoseconds)
    else:
        return logging.Formatter(formatter, style=style, datefmt=datefmt)


def get_formatter_string(formatter) -> str:
    """
    Function to get the formatter string from the 'logging.Formatter'.

    :param formatter: logging.Formatter, formatter to convert to string.
    :return: str, formatter string.
    """

    # noinspection PyProtectedMember
    return formatter._fmt

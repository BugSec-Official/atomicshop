import logging


# Log formatter, means how the log will look inside the file
# Format for specific object: %(levelname)s
# Format with adding spaces after the object with maximum of 10 characters: %(levelname)-10s
# Format with adding spaces before the object with maximum of 10 characters: %(levelname)10s

# ".40" truncating the string to only 40 characters. Example: %(message).250s

# Adding '%(asctime)s.%(msecs)06f' will print milliseconds as well as nanoseconds:
# 2022-02-17 15:15:51,913.335562
# If you don't use custom 'datefmt' in your 'setFormatter' function,
# it will print duplicate milliseconds:
# 2022-02-17 15:15:51,913.913.335562
# The setting should be like:
# file_handler.setFormatter(logging.Formatter(log_formatter_file, datefmt='%Y-%m-%d,%H:%M:%S'))
# 's' stands for string. 'd' stands for digits, a.k.a. 'int'. 'f' stands for float.

# Old tryouts:
#   log_formatter_file: str = f"%(asctime)s.%(msecs)06f | " \
#   log_formatter_file: str = f"%(asctime)s.%(msecs) | " \
#                           f"%(levelname)-{len(log_header_level)}s | " \
#                           f"%(name)-{len(log_header_logger)}s | " \
#                           f"%(filename)-{len(log_header_script)}s : " \
#                           f"%(lineno)-{len(log_header_line)}d | " \
#                           "%(threadName)s: %(message)s"
#   log_formatter_file: str = "{asctime}.{msecs:0<3.0f} | " \
#   log_formatter_file: str = "{asctime}.{msecs:0>3.0f}.{msecs:0>.6f} | " \

# Old tryouts for reference:
#   file_formatter = logging.Formatter(log_formatter_file, style='{')
#   file_formatter.default_time_format = '%Y-%m-%d %H:%M:%S'
#   file_formatter.default_msec_format = '%s,%03d'
#   file_formatter.default_msec_format = '%s,%03f'


FORMAT_ELEMENT_TO_HEADER: dict = {
    'asctime': 'Event Time [Y-M-D H:M:S]',
    'created': 'Created',
    'filename': "ModuleFileName            ",
    'funcName': 'Function',
    'levelname': 'Log Level',
    'levelno': 'Level Number',
    'lineno': 'Line ',
    'module': 'Module',
    'msecs': '[MS.mS]',
    'message': 'Message',
    'name': 'Logger Name                     ',
    'pathname': 'Path',
    'process': 'Process',
    'processName': 'Process Name',
    'relativeCreated': 'Relative Created',
    'thread': 'Thread',
    'threadName': 'Thread Name'
}

DEFAULT_FORMATTER_TXT_FILE: str = \
    "{asctime},{msecs:013.9f} | " \
    "{levelname:<" + f"{len(FORMAT_ELEMENT_TO_HEADER['levelname'])}" + "s} | " \
    "{name:<" + f"{len(FORMAT_ELEMENT_TO_HEADER['name'])}" + "s} | " \
    "{filename:<" + f"{len(FORMAT_ELEMENT_TO_HEADER['filename'])}" + "s} : " \
    "{lineno:<" + f"{len(FORMAT_ELEMENT_TO_HEADER['lineno'])}" + "d} | " \
    "{threadName} | {message}"

DEFAULT_FORMATTER_CSV_FILE: str = \
    '\"{asctime}.{msecs:010.6f}\",{levelname},{name},{filename},{lineno},{threadName},\"{message}\"'


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
            header_dict.update({element: FORMAT_ELEMENT_TO_HEADER[element]})

        return header_dict


def get_logging_formatter_from_string(
        formatter: str, style=None, datefmt=None, disable_duplicate_ms: bool = False) -> logging.Formatter:
    """
    Function to get the logging formatter from the string.

    :param formatter: string formatter to convert to 'logging.Formatter'.
    :param style: string, style of the formatter. Default is None.
        None: will try to detect the style.
        '%': will use the '%' style.
        '{': will use the '{' style.
    :param datefmt: string, date format of 'asctime' element. Default is None.
    :param disable_duplicate_ms: bool, if True, will disable the duplicate milliseconds in the 'asctime' element.
        Example: If we're using '%(asctime)s.%(msecs)06f' msecs value in our time stamp, we need to use custom
            'datefmt' to get rid of the additional duplicate milliseconds:
            Instead of '2022-02-17 15:15:51,913.913.335562' print '2022-02-17 15:15:51,913.335562'
            The problem with this method is that milliseconds aren't adjusted to 3 digits with zeroes (like 1 = 001).
            We can use the regular strftime format: datefmt='%Y-%m-%d,%H:%M:%S:%f'
    :return: logging.Formatter, formatter.
    """

    # If the style is not defined, get it.
    if not style:
        style = FormatterProcessor(formatter).get_style()['style']

    # The regular 'datefmt' is '%Y-%m-%d,%H:%M:%S:%f'. If we want to use it with milliseconds 'msecs' element,
    # we need to disable the duplicate milliseconds.
    if disable_duplicate_ms:
        datefmt = '%Y-%m-%d,%H:%M:%S'

    # Create the logging formatter.
    return logging.Formatter(formatter, style=style, datefmt=datefmt)

import logging
from logging.handlers import TimedRotatingFileHandler, QueueListener, QueueHandler
from logging import FileHandler
import time
import re
import os
from pathlib import Path
import queue
from typing import Literal, Union
import threading
from datetime import datetime

from . import loggers, formatters
from ... import datetimes, filesystem


DEFAULT_DATE_STRING_FORMAT: str = "%Y_%m_%d"
# Not used, only for the reference:
# _DEFAULT_DATE_REGEX_PATTERN: str = r"^\d{4}_\d{2}_\d{2}$"


class ForceAtTimeRotationTimedRotatingFileHandler(TimedRotatingFileHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_rotated_date = None
        self._start_rotation_check()

    def _start_rotation_check(self):
        self._rotation_thread = threading.Thread(target=self._check_for_rotation)
        self._rotation_thread.daemon = True
        self._rotation_thread.start()

    def _check_for_rotation(self):
        while True:
            now = datetime.now()
            current_date = now.date()
            # Check if it's midnight and the logs haven't been rotated today
            if now.hour == 0 and now.minute == 0 and current_date != self._last_rotated_date:
                self._last_rotated_date = current_date
                self.doRollover()
            time.sleep(0.1)

    def doRollover(self):
        super().doRollover()


class TimedRotatingFileHandlerWithHeader(ForceAtTimeRotationTimedRotatingFileHandler):
    """
    Custom TimedRotatingFileHandler that writes a header to the log file each time there is a file rotation.
    Useful for writing CSV files.

    :param header: string, Header to write to the log file.
        Example: "time,host,error"
    """
    def __init__(self, *args, **kwargs):
        self.header = kwargs.pop('header', None)
        super().__init__(*args, **kwargs)

    def doRollover(self):
        super().doRollover()
        self._write_header()

    def _write_header(self):
        if self.header:
            with open(self.baseFilename, 'a') as f:
                f.write(self.header + '\n')

    def emit(self, record):
        if not os.path.exists(self.baseFilename) or os.path.getsize(self.baseFilename) == 0:
            self._write_header()
        super().emit(record)


def _process_formatter_attribute(
        formatter: Union[
            Literal['DEFAULT', 'MESSAGE'],
            str,
            None],
        file_type: Union[
            Literal['txt', 'csv', 'json'],
            None] = None
):
    """
    Function to process the formatter attribute.
    """

    if formatter == 'DEFAULT' and file_type is None:
        return formatters.DEFAULT_STREAM_FORMATTER
    elif formatter == 'DEFAULT' and file_type == 'txt':
        return formatters.DEFAULT_FORMATTER_TXT_FILE
    elif formatter == 'DEFAULT' and file_type == 'csv':
        return formatters.DEFAULT_FORMATTER_CSV_FILE
    elif formatter == 'DEFAULT' and file_type == 'json':
        return formatters.DEFAULT_MESSAGE_FORMATTER
    elif formatter == 'MESSAGE':
        return formatters.DEFAULT_MESSAGE_FORMATTER
    else:
        return formatter


def add_stream_handler(
        logger: logging.Logger,
        logging_level: str = "DEBUG",
        formatter: Union[
            Literal['DEFAULT', 'MESSAGE'],
            str,
            None] = None,
        formatter_use_nanoseconds: bool = False
):
    """
    Function to add StreamHandler to logger.
    Stream formatter will output messages to the console.
    """

    # Getting the StreamHandler.
    stream_handler = get_stream_handler()
    # Setting log level for the handler, that will use the logger while initiated.
    loggers.set_logging_level(stream_handler, logging_level)

    # If formatter_message_only is set to True, then formatter will be used only for the 'message' part.
    formatter = _process_formatter_attribute(formatter)

    # If formatter was provided, then it will be used.
    if formatter:
        logging_formatter = formatters.get_logging_formatter_from_string(
            formatter=formatter, use_nanoseconds=formatter_use_nanoseconds)
        set_formatter(stream_handler, logging_formatter)

    # Adding the handler to the main logger
    loggers.add_handler(logger, stream_handler)

    # Disable propagation from the 'root' logger, so we will not see the messages twice.
    loggers.set_propagation(logger)


def add_timedfilehandler_with_queuehandler(
        logger: logging.Logger,
        file_path: str,
        file_type: Literal[
            'txt',
            'csv',
            'json'] = 'txt',
        logging_level="DEBUG",
        formatter: Union[
            Literal['DEFAULT', 'MESSAGE'],
            str,
            None] = None,
        formatter_use_nanoseconds: bool = False,
        when: str = 'midnight',
        interval: int = 1,
        delay: bool = True,
        encoding=None,
        header: str = None
):
    """
    Function to add TimedRotatingFileHandler and QueueHandler to logger.
    TimedRotatingFileHandler will output messages to the file through QueueHandler.
    This is needed, since TimedRotatingFileHandler is not thread-safe, though official docs say it is.
    """

    # If file name wasn't provided we will use the logger name instead.
    # if not file_name_no_extension:
    #     file_name_no_extension = logger.name

    # Setting the TimedRotatingFileHandler, without adding it to the logger.
    # It will be added to the QueueListener, which will use the TimedRotatingFileHandler to write logs.
    # This is needed since there's a bug in TimedRotatingFileHandler, which won't let it be used with
    # threads the same way it would be used for multiprocess.

    # Creating file handler with log filename. At this stage the log file is created and locked by the handler,
    # Unless we use "delay=True" to tell the class to write the file only if there's something to write.

    filesystem.create_directory(os.path.dirname(file_path))

    if file_type == "csv":
        # If file extension is CSV, we'll set the header to the file.
        # This is needed since the CSV file will be rotated, and we'll need to set the header each time.
        # We'll use the custom TimedRotatingFileHandlerWithHeader class.
        file_handler = get_timed_rotating_file_handler_with_header(
            file_path, when=when, interval=interval, delay=delay, encoding=encoding, header=header)
    else:
        file_handler = get_timed_rotating_file_handler(
            file_path, when=when, interval=interval, delay=delay, encoding=encoding)

    loggers.set_logging_level(file_handler, logging_level)

    formatter = _process_formatter_attribute(formatter, file_type=file_type)

    # If formatter was passed to the function we'll add it to handler.
    if formatter:
        # Convert string to Formatter object. Moved to newer styling of python 3: style='{'
        logging_formatter = formatters.get_logging_formatter_from_string(
            formatter=formatter, use_nanoseconds=formatter_use_nanoseconds)
        # Setting the formatter in file handler.
        set_formatter(file_handler, logging_formatter)

    # This function will change the suffix behavior of the rotated file name.
    change_rotated_filename(file_handler)

    queue_handler = start_queue_listener_for_file_handler_and_get_queue_handler(file_handler)
    loggers.set_logging_level(queue_handler, logging_level)

    # Add the QueueHandler to the logger.
    loggers.add_handler(logger, queue_handler)

    # Disable propagation from the 'root' logger, so we will not see the messages twice.
    loggers.set_propagation(logger)


def start_queue_listener_for_file_handler_and_get_queue_handler(file_handler):
    """
    Function to start QueueListener, which will put the logs from FileHandler to the Queue.
    QueueHandler will get the logs from the Queue and put them to the file that was set in the FileHandler.

    :param file_handler: FileHandler object.
    :return: QueueHandler object.
    """

    # Create the Queue between threads. "-1" means that there can infinite number of items that can be
    # put in the Queue. if integer is bigger than 0, it means that this will be the maximum
    # number of items.
    queue_object = queue.Queue(-1)
    # Create QueueListener, which will put the logs from FileHandler to the Queue and put the logs to the queue.
    start_queue_listener_for_file_handler(file_handler, queue_object)

    return get_queue_handler(queue_object)


# BASE FUNCTIONS =======================================================================================================


def get_stream_handler() -> logging.StreamHandler:
    """
    Function to get a StreamHandler.
    This handler that will output messages to the console.

    :return: StreamHandler.
    """

    return logging.StreamHandler()


def get_timed_rotating_file_handler(
        log_file_path: str, when: str = "midnight", interval: int = 1, delay: bool = False, encoding=None
) -> ForceAtTimeRotationTimedRotatingFileHandler:
    """
    Function to get a TimedRotatingFileHandler.
    This handler will output messages to a file, rotating the log file at certain timed intervals.

    :param log_file_path: Path to the log file.
    :param when: When to rotate the log file. Possible values:
        "S" - Seconds
        "M" - Minutes
        "H" - Hours
        "D" - Days
        "midnight" - Roll over at midnight
    :param interval: Interval to rotate the log file.
    :param delay: bool, If set to True, the log file will be created only if there's something to write.
    :param encoding: Encoding to use for the log file. Same as for the TimeRotatingFileHandler, which uses Default None.
    :return: TimedRotatingFileHandler.
    """

    return ForceAtTimeRotationTimedRotatingFileHandler(
        filename=log_file_path, when=when, interval=interval, delay=delay, encoding=encoding)


def get_timed_rotating_file_handler_with_header(
        log_file_path: str, when: str = "midnight", interval: int = 1, delay: bool = False, encoding=None,
        header: str = None) -> TimedRotatingFileHandlerWithHeader:
    """
    Function to get a TimedRotatingFileHandler with header.
    This handler will output messages to a file, rotating the log file at certain timed intervals.
    It will write a header to the log file each time there is a file rotation.

    :param log_file_path: Path to the log file.
    :param when: When to rotate the log file. Possible
    :param interval: Interval to rotate the log file.
    :param delay: bool, If set to True, the log file will be created only if there's something to write.
    :param encoding: Encoding to use for the log file. Same as for the TimeRotatingFileHandler, which uses Default None.
    :param header: Header to write to the log file.
        Example: "time,host,error"
    :return: TimedRotatingFileHandlerWithHeader.
    """

    return TimedRotatingFileHandlerWithHeader(
        filename=log_file_path, when=when, interval=interval, delay=delay, encoding=encoding, header=header)


def start_queue_listener_for_file_handler(
        file_handler: logging.FileHandler, queue_object) -> logging.handlers.QueueListener:
    """
    Function to get a QueueListener for the FileHandler.
    This handler get the messages from the FileHandler and put them in the Queue.

    :param file_handler: FileHandler to get the messages from.
    :param queue_object: Queue object to put the messages in.
    :return: QueueListener.
    """

    # Create the QueueListener based on TimedRotatingFileHandler
    queue_listener = QueueListener(queue_object, file_handler)
    # Start the QueueListener. Each logger will have its own instance of the Queue
    queue_listener.start()

    return queue_listener


def get_queue_handler(queue_object) -> logging.handlers.QueueHandler:
    """
    Function to get a QueueHandler.
    This handler gets the messages from the Queue and writes them to file of the FileHandler that was set for
    QueueListener.

    :param queue_object: Queue object to get the messages from.
    :return: QueueHandler.
    """

    return QueueHandler(queue_object)


def set_formatter(handler: logging.Handler, logging_formatter: logging.Formatter):
    """
    Function to set the formatter for the handler.
    :param handler: Handler to set the formatter to.
    :param logging_formatter: logging Formatter to set to the handler.
    """

    handler.setFormatter(logging_formatter)


def set_handler_name(handler: logging.Handler, handler_name: str):
    """
    Function to set the handler name.
    :param handler: Handler to set the name to.
    :param handler_name: Name to set to the handler.
    """

    handler.set_name(handler_name)


def get_handler_name(handler: logging.Handler) -> str:
    """
    Function to get the handler name.
    :param handler: Handler to get the name from.
    :return: Handler name.
    """

    return handler.get_name()


def change_rotated_filename(
        file_handler: logging.Handler,
        date_format_string: str = None
):
    """
    Function to change the way TimedRotatingFileHandler managing the rotating filename.

    :param file_handler: FileHandler to change the rotating filename for.
    :param date_format_string: Date format string to use for the rotated log filename.
        If None, the default 'DEFAULT_DATE_STRING_FORMAT' will be used.
    """
    # Changing the way TimedRotatingFileHandler managing the rotating filename
    # Default file suffix is only "Year_Month_Day" with addition of the dot (".") character to the
    # "file name + extension" that you provide it. Example: log file name:
    # test.log
    # After file is rotated at midnight, by default the old filename will be:
    # test.log.2021_12_24
    # And the log file of 25th, now will be "test.log".
    # So, Changing the file suffix to include the extension to the suffix, so it will be:
    # test.log.2021_12_24.log
    # file_handler.suffix = logfile_suffix
    # file_handler.suffix = "_%Y_%m_%d.txt"
    # This step will remove the created ".log." above before the suffix and the filename will look like:
    # test.2021_12_24.log
    # file_handler.namer = lambda name: name.replace(log_file_extension + ".", "") + log_file_extension
    # file_handler.namer = lambda name: name.replace(".txt.", "") + log_file_extension
    # This will recompile the string to tell the handler the length of the suffix parts
    # file_handler.extMatch = re.compile(r"^\d{4}_\d{2}_\d{2}" + re.escape(log_file_extension) + r"$")
    # file_handler.extMatch = re.compile(r"^\d{4}_\d{2}_\d{2}.txt$")

    def callback_namer(name):
        """
        Callback function to change the filename of the rotated log file on file rotation.
        """
        # Currently the 'name' is full file path + '.' + logfile_suffix.
        # Example: 'C:\\path\\to\\file.log._2021_12_24'
        # Get the parent directory of the file: C:\path\to
        parent_dir: str = str(Path(name).parent)
        # Get the base filename without the extension: file.log
        filename: str = Path(name).stem
        # Get the date part of the filename: _2021_12_24
        date_part: str = str(Path(name).suffix).replace(".", "")
        # Get the file extension: log
        file_extension: str = Path(filename).suffix
        # Get the file name without the extension: file
        file_stem: str = Path(filename).stem

        return f"{parent_dir}{os.sep}{file_stem}{date_part}{file_extension}"

    if date_format_string is None:
        date_format_string = DEFAULT_DATE_STRING_FORMAT

    # Construct the new suffix without the file extension
    logfile_suffix = f"_{date_format_string}"

    # Get regex pattern from string format.
    # Example: '%Y_%m_%d' -> r'\d{4}_\d{2}_\d{2}'
    date_regex_pattern = datetimes.datetime_format_to_regex(date_format_string)

    # Regex pattern to match the rotated log filenames
    logfile_regex_suffix = re.compile(date_regex_pattern)

    # Update the handler's suffix to include the date format
    file_handler.suffix = logfile_suffix

    file_handler.namer = callback_namer
    # Update the handler's extMatch regex to match the new filename format
    file_handler.extMatch = logfile_regex_suffix


def has_handlers(logger: logging.Logger) -> bool:
    """
    Function to check if the logger has handlers.
    :param logger: Logger to check
    :return: True if logger has handlers, False otherwise
    """

    # Omitted the usage of "hasHandlers()" method, since sometimes returned "True" even when there were no handlers
    # Didn't research the issue much, just used the "len(logger.handlers)" to check how many handlers there are
    # in the logger.
    # if not logging.getLogger(function_module_name).hasHandlers():
    # if len(logging.getLogger(function_module_name).handlers) == 0:

    if len(logger.handlers) == 0:
        return False
    else:
        return True


def extract_datetime_format_from_file_handler(file_handler: FileHandler) -> Union[str, None]:
    """
    Extract the datetime string formats from all TimedRotatingFileHandlers in the logger.

    Args:
    - logger: The logger instance.

    Returns:
    - A list of datetime string formats used by the handlers.
    """
    # Extract the suffix
    suffix = getattr(file_handler, 'suffix', None)
    if suffix:
        datetime_format = datetimes.extract_datetime_format_from_string(suffix)
        if datetime_format:
            return datetime_format

        return None

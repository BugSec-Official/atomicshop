import logging
from logging.handlers import TimedRotatingFileHandler, QueueListener, QueueHandler
import time
import re
import os
from pathlib import Path
import queue
from typing import Literal, Union
import threading
from datetime import datetime
import contextlib
import multiprocessing

from . import loggers, formatters, filters, consts
from ... import datetimes, filesystem


r"""
# Not used, only for the reference:
DEFAULT_DATE_STRING_FORMAT: str = "%Y_%m_%d"
DEFAULT_DATE_REGEX_PATTERN: str = r"^\d{4}_\d{2}_\d{2}$"
"""


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
        return consts.DEFAULT_STREAM_FORMATTER
    elif formatter == 'DEFAULT' and file_type == 'txt':
        return consts.DEFAULT_FORMATTER_TXT_FILE
    elif formatter == 'DEFAULT' and file_type == 'csv':
        return consts.DEFAULT_FORMATTER_CSV_FILE
    elif formatter == 'DEFAULT' and file_type == 'json':
        return consts.DEFAULT_MESSAGE_FORMATTER
    elif formatter == 'MESSAGE':
        return consts.DEFAULT_MESSAGE_FORMATTER
    else:
        return formatter


def get_stream_handler_extended(
        logging_level: str = "DEBUG",
        formatter: Union[
            Literal['DEFAULT', 'MESSAGE'],
            str,
            None] = None,
        formatter_use_nanoseconds: bool = False
) -> logging.StreamHandler:
    """
    Function to get StreamHandler with extended configuration.
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

    return stream_handler


# Function to start the interval-based rotation check
def _start_interval_rotation(handler):
    # def check_rotation():
    #     while True:
    #         next_rollover = _calculate_next_rollover()
    #         while datetime.now() < next_rollover:
    #             time.sleep(0.1)
    #
    #             # Check if the next_rollover has changed (indicating a rollover by an event)
    #             if _calculate_next_rollover() != next_rollover:
    #                 next_rollover = _calculate_next_rollover()
    #                 break
    #
    #         # Perform manual rollover if needed
    #         if datetime.now() >= next_rollover:
    #             handler.doRollover()
    #
    #         # handler.doRollover()
    #
    # def _calculate_next_rollover():
    #     return datetime.fromtimestamp(handler.rolloverAt)
    def check_rotation():
        last_rollover_at = handler.rolloverAt  # Initial rollover time

        while True:
            current_time = datetime.now()
            next_rollover = datetime.fromtimestamp(handler.rolloverAt)

            # Check if the rollover time has passed and it hasn't been handled yet
            if current_time >= next_rollover and handler.rolloverAt == last_rollover_at:
                # Perform manual rollover
                handler.doRollover()

                # Update last_rollover_at to the new rolloverAt
                last_rollover_at = handler.rolloverAt

            # Sleep for a short interval before checking again
            time.sleep(0.1)

    rotation_thread = threading.Thread(target=check_rotation)
    rotation_thread.daemon = True
    rotation_thread.start()


def _wrap_do_rollover(handler, header):
    original_do_rollover = handler.doRollover

    def new_do_rollover():
        original_do_rollover()
        # After rollover, write the header
        if header:
            with open(handler.baseFilename, 'a') as f:
                f.write(header + '\n')

    handler.doRollover = new_do_rollover


def get_queue_handler_and_start_queue_listener_for_file_handler(file_handler):
    """
    Function to create QueueHandler and start QueueListener for the FileHandler.
    The QueueListener, which will get the logs from the queue and use the FileHandler to write them to the
    file.
    The QueueHandler will put the logs to the queue.

    :param file_handler: FileHandler object.
    :return: QueueHandler object.
    """

    # Create the Queue between threads. "-1" means that there can infinite number of items that can be
    # put in the Queue. if integer is bigger than 0, it means that this will be the maximum
    # number of items.
    queue_object = queue.Queue(-1)

    # Create QueueListener, which will get the logs from the queue and use the FileHandler to write them to the file.
    start_queue_listener_for_handlers((file_handler,), queue_object)

    # Get the QueueHandler, which will put the logs to the queue.
    queue_handler = get_queue_handler(queue_object)

    return queue_handler


# BASE FUNCTIONS =======================================================================================================


def get_stream_handler() -> logging.StreamHandler:
    """
    Function to get a StreamHandler.
    This handler that will output messages to the console.

    :return: StreamHandler.
    """

    return logging.StreamHandler()


# noinspection PyPep8Naming
def get_timed_rotating_file_handler(
        log_file_path: str,
        when: str = "midnight",
        interval: int = 1,
        backupCount: int = 0,
        delay: bool = False,
        encoding=None
) -> TimedRotatingFileHandler:
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
    :param backupCount: int, Number of backup files to keep. Default is 0.
        If backupCount is > 0, when rollover is done, no more than backupCount files are kept, the oldest are deleted.
        If backupCount is == 0, all the backup files will be kept.
    :param delay: bool, If set to True, the log file will be created only if there's something to write.
    :param encoding: Encoding to use for the log file. Same as for the TimeRotatingFileHandler, which uses Default None.
    :return: TimedRotatingFileHandler.
    """

    return TimedRotatingFileHandler(
        filename=log_file_path, when=when, interval=interval, backupCount=backupCount, delay=delay, encoding=encoding)


# noinspection PyPep8Naming
def get_timed_rotating_file_handler_extended(
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
        rotate_at_rollover_time: bool = True,
        rotation_date_format: str = None,
        rotation_callback_namer_function: callable = None,
        rotation_use_default_callback_namer_function: bool = True,
        use_internal_queue_listener: bool = False,
        when: str = 'midnight',
        interval: int = 1,
        delay: bool = True,
        backupCount: int = 0,
        encoding=None,
        header: str = None
) -> Union[TimedRotatingFileHandler, logging.handlers.QueueHandler]:
    """
    :param file_path: Path to the log file.
    :param file_type: Type of the file. Possible values: 'txt', 'csv', 'json'.
    :param logging_level: Logging level for the handler.
    :param formatter: Formatter for the handler.
    :param formatter_use_nanoseconds: If set to True, the formatter will use nanoseconds.
    :param rotate_at_rollover_time: If set to True, the handler will rotate the log file at the rollover time.
    :param rotation_date_format: Date format string to set to the handler's suffix.
    :param rotation_callback_namer_function: Callback function to change the filename on rotation.
    :param rotation_use_default_callback_namer_function: If set to True, the default callback namer function will be used
        and the filename will be changed on rotation instead of using the default like this:
        'file.log.2021-12-24' -> 'file_2021-12-24.log'.
    :param use_internal_queue_listener: If set to True, the handler will use internal QueueListener to write logs.
    :param when: When to rotate the log file. Possible values:
        "S" - Seconds
        "M" - Minutes
        "H" - Hours
        "D" - Days
        "midnight" - Roll over at midnight
    :param use_internal_queue_listener: If set to True, the handler will use internal QueueListener to write logs.
        Function to add TimedRotatingFileHandler and QueueHandler to logger.
        TimedRotatingFileHandler will output messages to the file through QueueHandler.
        This is needed, since TimedRotatingFileHandler is not thread-safe, though official docs say it is.
    :param interval: Interval to rotate the log file.
    :param delay: If set to True, the log file will be created only if there's something to write.
    :param backupCount: Number of backup files to keep. Default is 0.
        If backupCount is > 0, when rollover is done, no more than backupCount files are kept, the oldest are deleted.
        If backupCount is == 0, all the backup files will be kept.
    :param encoding: Encoding to use for the log file. Same as for the TimeRotatingFileHandler, which uses Default None.
    :param header: Header to write to the log file.
    :return: TimedRotatingFileHandler or QueueHandler (if, use_internal_queue_listener is set to True).
    """

    # Creating file handler with log filename. At this stage the log file is created and locked by the handler,
    # Unless we use "delay=True" to tell the class to write the file only if there's something to write.

    filesystem.create_directory(os.path.dirname(file_path))

    file_handler = get_timed_rotating_file_handler(
        file_path, when=when, interval=interval, delay=delay, backupCount=backupCount, encoding=encoding)

    loggers.set_logging_level(file_handler, logging_level)

    formatter = _process_formatter_attribute(formatter, file_type=file_type)

    # If formatter was passed to the function we'll add it to handler.
    # noinspection GrazieInspection
    if formatter:
        # Convert string to Formatter object. Moved to newer styling of python 3: style='{'.
        logging_formatter = formatters.get_logging_formatter_from_string(
            formatter=formatter, use_nanoseconds=formatter_use_nanoseconds)
        # Setting the formatter in file handler.
        set_formatter(file_handler, logging_formatter)

    # This function will change the suffix behavior of the rotated file name.
    change_rotated_filename(
        file_handler=file_handler, date_format_string=rotation_date_format,
        callback_namer_function=rotation_callback_namer_function,
        use_default_callback_namer_function=rotation_use_default_callback_namer_function
    )

    # If header is set, we'll add the filter to the handler that will create the header on file rotation.
    if header:
        # Filter is added to write header on logger startup.
        add_filter_to_handler(file_handler, filters.HeaderFilter(header, file_handler.baseFilename))
        # Wrap the doRollover method to write the header after each rotation, since adding the filter
        # will only write the header on log file creation.
        _wrap_do_rollover(file_handler, header)

    # Start the interval-based rotation forcing.
    if rotate_at_rollover_time:
        _start_interval_rotation(file_handler)

    # Setting the TimedRotatingFileHandler, without adding it to the logger.
    # It will be added to the QueueListener, which will use the TimedRotatingFileHandler to write logs.
    # This is needed since there's a bug in TimedRotatingFileHandler, which won't let it be used with
    # threads the same way it would be used for multiprocess.

    # If internal queue listener is set to True, we'll start the QueueListener for the FileHandler.
    if use_internal_queue_listener:
        queue_handler = get_queue_handler_and_start_queue_listener_for_file_handler(file_handler)
        loggers.set_logging_level(queue_handler, logging_level)
        return queue_handler
    else:
        return file_handler


def start_queue_listener_for_handlers(
        handlers: tuple[logging.Handler],
        queue_object: Union[queue.Queue, multiprocessing.Queue]
) -> logging.handlers.QueueListener:
    """
    Function to get a QueueListener for the FileHandler.
    This handler get the messages from the FileHandler and put them in the Queue.

    :param handlers: Tuple of handlers to put in the QueueListener.
        For example, it can be (stream_handler, file_handler).
    :param queue_object: Queue object to put the messages in.
    :return: QueueListener.
    """

    # Create the QueueListener based on TimedRotatingFileHandler
    queue_listener: logging.handlers.QueueListener = QueueListener(queue_object, *handlers)
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


def get_queue_handler_extended(
        queue_object: Union[
            queue.Queue,
            multiprocessing.Queue],
        logging_level: str = "DEBUG"):
    """
    Function to get the QueueHandler.
    QueueHandler of the logger will pass the logs to the Queue and the opposite QueueListener will write them
    from the Queue to the file that was set in the FileHandler.
    """

    # Getting the QueueHandler.
    queue_handler = get_queue_handler(queue_object)
    # Setting log level for the handler, that will use the logger while initiated.
    loggers.set_logging_level(queue_handler, logging_level)

    return queue_handler


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
        date_format_string: str = None,
        callback_namer_function: callable = None,
        use_default_callback_namer_function: bool = True
):
    """
    Function to change the way TimedRotatingFileHandler managing the rotating filename.

    :param file_handler: FileHandler to change the rotating filename for.
    :param date_format_string: Date format string to set to the handler's suffix.
    :param callback_namer_function: Callback function to change the filename on rotation.
    :param use_default_callback_namer_function: If set to True, the default callback namer function will be used
        and the filename will be changed on rotation instead of using the default like this:
        'file.log.2021-12-24' -> 'file_2021-12-24.log'.

    ---------------------

    At this point, 'file_handler.suffix' is already '%Y-%m-%d' if 'when' is set to 'midnight'.
    You can change it if you wish (example: '%Y_%m_%d'), the method is described below.
    """

    def callback_namer(name):
        """
        Callback function to change the filename of the rotated log file on file rotation.
        """
        # Currently the 'name' is full file path + '.' + logfile_suffix.
        # Example: 'C:\\path\\to\\file.log.2021-12-24'
        # Get the parent directory of the file: C:\path\to
        parent_dir: str = str(Path(name).parent)
        # Get the base filename without the extension: file.log
        filename: str = Path(name).stem
        # Get the date part of the filename: 2021-12-24
        date_part: str = str(Path(name).suffix).replace(".", "")
        # Get the file extension: log
        file_extension: str = Path(filename).suffix
        # Get the file name without the extension: file
        file_stem: str = Path(filename).stem

        return f"{parent_dir}{os.sep}{file_stem}_{date_part}{file_extension}"

    def change_file_handler_suffix():
        # Get regex pattern from string format.
        # Example: '%Y_%m_%d' -> r'\d{4}_\d{2}_\d{2}'
        date_regex_pattern = datetimes.datetime_format_to_regex(date_format_string)

        # Regex pattern to match the rotated log filenames
        logfile_regex_suffix = re.compile(date_regex_pattern)

        # Update the handler's suffix to include the date format
        file_handler.suffix = date_format_string

        # Update the handler's extMatch regex to match the new filename format
        file_handler.extMatch = logfile_regex_suffix

    if use_default_callback_namer_function and callback_namer_function:
        raise ValueError("You can't use both default and custom callback namer function.")
    elif not use_default_callback_namer_function and not callback_namer_function:
        raise ValueError(
            "You need to provide a 'callback_namer_function' or our 'use_default_callback_namer_function'.")

    if date_format_string:
        change_file_handler_suffix()

    # Set the callback function to change the filename on rotation.
    if use_default_callback_namer_function:
        file_handler.namer = callback_namer

    if callback_namer_function:
        file_handler.namer = callback_namer_function


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


def extract_datetime_format_from_file_handler(file_handler: logging.FileHandler) -> Union[str, None]:
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


def add_filter_to_handler(handler: logging.Handler, filter_object: logging.Filter):
    """
    Function to add a filter to the handler.
    :param handler: Handler to add the filter to.
    :param filter_object: Filter object to add to the handler.
    """

    handler.addFilter(filter_object)


def get_formatter_string(handler: logging.Handler) -> str:
    """
    Function to get the formatter string from the handler.
    :param handler: Handler to get the formatter from.
    :return: Formatter string.
    """

    return formatters.get_formatter_string(handler.formatter)


@contextlib.contextmanager
def temporary_change_formatter(handler: logging.Handler, formatter_string: str):
    """
    Context manager to temporarily change the formatter of the handler.

    Example:
        with temporary_change_formatter(handler, formatter_string):
            # Do something with the temporary formatter.
            pass
    """
    original_formatter = handler.formatter

    try:
        handler.setFormatter(logging.Formatter(formatter_string))
        yield
    finally:
        handler.setFormatter(original_formatter)
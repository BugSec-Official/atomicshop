import logging
import os
from typing import Literal, Union
import datetime
import contextlib
import threading

from . import loggers, handlers
from ...file_io import csvs
from ...basics import tracebacks, ansi_escape_codes
from ... import print_api


class LoggingwLoggerAlreadyExistsError(Exception):
    pass


# noinspection PyPep8Naming
def create_logger(
        logger_name: str,
        file_path: str = None,
        directory_path: str = None,
        add_stream: bool = False,
        add_timedfile: bool = False,
        file_type: Literal[
            'txt',
            'csv',
            'json'] = 'txt',
        logging_level="DEBUG",
        formatter_streamhandler: Union[
            Literal['MESSAGE', 'DEFAULT'],
            str,
            None] = None,
        formatter_filehandler: Union[
            Literal['MESSAGE', 'DEFAULT'],
            str,
            None] = None,
        formatter_streamhandler_use_nanoseconds: bool = True,
        formatter_filehandler_use_nanoseconds: bool = True,
        filehandler_rotate_at_rollover_time: bool = True,
        filehandler_rotation_date_format: str = None,
        filehandler_rotation_callback_namer_function: callable = None,
        filehandler_rotation_use_default_namer_function: bool = True,
        when: str = "midnight",
        interval: int = 1,
        backupCount: int = 0,
        delay: bool = False,
        encoding=None,
        header: str = None
) -> logging.Logger:
    """
    Function to get a logger and add StreamHandler and TimedRotatingFileHandler to it.

    :param logger_name: Name of the logger.
    :param file_path: full path to the log file. If you don't want to use the file, set it to None.
        You can set the directory_path only and then the 'logger_name' will be used as the file name with the
        'file_type' as the file extension.
    :param directory_path: full path to the directory where the log file will be saved.
    :param add_stream: bool, If set to True, StreamHandler will be added to the logger.
    :param add_timedfile: bool, If set to True, TimedRotatingFileHandler will be added to the logger.
    :param file_type: string, file type of the log file. Default is 'txt'.
        'txt': Text file.
        'csv': CSV file.
        'json': JSON file.
    :param logging_level: str or int, Logging level for the handler, that will use the logger while initiated.
    :param formatter_streamhandler: string, Formatter to use for StreamHandler. It is template of how a message will
        look like.
        None: No formatter will be used.
        'DEFAULT': Default formatter will be used:
            "%(levelname)s | %(threadName)s | %(name)s | %(message)s"
        'MESSAGE': Formatter will be used only for the 'message' part.
        string: Custom formatter, regular syntax for logging.Formatter.
    :param formatter_filehandler: string, Formatter to use for handler. It is template of how a message will look like.
        None: No formatter will be used.
        'DEFAULT': Default formatter will be used for each file extension:
            txt: "%(asctime)s | %(levelname)s | %(threadName)s | %(name)s | %(message)s"
            csv: "%(asctime)s,%(levelname)s,%(threadName)s,%(name)s,%(message)s"
            json: '{"time": "%(asctime)s", "level": "%(levelname)s", "thread": "%(threadName)s",
                "logger": "%(name)s", "message": "%(message)s"}'
        'MESSAGE': Formatter will be used only for the 'message' part.
        string: Custom formatter, regular syntax for logging.Formatter.
    :param formatter_streamhandler_use_nanoseconds: bool, If set to True, the nanoseconds will be used
        in the formatter in case you provide 'asctime' element.
    :param formatter_filehandler_use_nanoseconds: bool, If set to True, the nanoseconds will be used
        in the formatter in case you provide 'asctime' element.
    :param filehandler_rotate_at_rollover_time: bool,
        If set to True, the log file will be rotated at the rollover time, even if there's nothing to write.
            This behavior overrides the TimedRotatingFileHandler default behavior on doRollover.
        If set to False, the log file will be rotated after 'when' time, but only when event occurs.
            This is the default doRollover behavior of the TimedRotatingFileHandler.
    :param filehandler_rotation_date_format: string, Date format to use for the log file rotation.
        Example for 'when="midnight"': the default date format is '%Y-%m-%d', resulting in filename on rotation like:
            "test.log.2021-11-25"
            If you want to change the date format to '%Y_%m_%d', the filename will be:
            "test.log.2021_11_25"
    :param filehandler_rotation_callback_namer_function: callable, Callback function to use for the log file naming
        on rotation. If set to None, logging module default function will be used. With "when='midnight'",
        and filename: "test.log" this will name the file on rotation similar to: "test.log.2021-11-25".
    :param filehandler_rotation_use_default_namer_function: bool, If set to True, the default namer function will be
        used for the log file naming on rotation. With "when='midnight'" and filename: "test.log",
        this will name the file on rotation similar to: "test_2021-11-25.log".
    :param when: string, When to rotate the log file. Default is 'midnight'.
        [when="midnight"] is set to rotate the filename at midnight. This means that the current file name will be
        added Yesterday's date to the end of the file and today's file will continue to write at the same
        filename. Also, if the script finished working on 25.11.2021, the name of the log file will be "test.log"
        If you run the script again on 28.11.2021, the logging module will take the last modification date of
        the file "test.log" and assign a date to it: test.log.2021_11_25
        The log filename of 28.11.2021 will be called "test.log" again.
    :param interval: int, Interval to rotate the log file. Default is 1.
        If 'when="midnight"' and 'interval=1', then the log file will be rotated every midnight.
        If 'when="midnight"' and 'interval=2', then the log file will be rotated every 2nd midnights.
    :param backupCount: int, Number of backup files to keep. Default is 0.
        If backupCount is > 0, when rollover is done, no more than backupCount files are kept, the oldest are deleted.
        If backupCount is == 0, all the backup files will be kept.
    :param delay: bool, If set to True, the log file will be created only if there's something to write.
    :param encoding: string, Encoding to use for the log file. Default is None.
    :param header: string, Header to write to the log file.
        Example: "time,host,error"
        Useful for 'csv' file type format.

    :return: Logger.

    ================================================================================================================

    Working example to write CSV logs to the file and output messages to the console:
    from atomicshop.wrappers.loggingw import loggingw


    def main():
        header: str = "time,host,error"
        output_log_file: str = "D:\\logs\\log_file.csv"

        error_logger = loggingw.create_logger(
            logger_name=f'{self.__class__.__name__}_CSV',
            file_path=output_log_file,
            add_timedfile=True,
            file_type='csv',
            formatter_filehandler='MESSAGE',
            header=header
        )

        error_logger.info(error_message)


    if __name__ == "__main__":
        main()

    ------------------------------

    Example to use StreamHandler to output to console and TimedRotatingFileHandler to write to file:
    from atomicshop.wrappers.loggingw import loggingw


    def main():
        header: str = "time,host,error"
        output_log_file: str = "D:\\logs\\log_file.txt"

        error_logger = loggingw.create_logger(
            logger_name=f'{self.__class__.__name__}',
            file_path=output_log_file,
            add_stream=True,
            add_timedfile=True,
            file_type='txt',
            formatter_streamhandler='DEFAULT',
            formatter_filehandler='DEFAULT'
        )

        error_logger.info(f"{datetime.now()},host1,/path/to/file,error message")


    if __name__ == "__main__":
        main()
    """

    # Check if the logger exists before creating it.
    if loggers.is_logger_exists(logger_name):
        raise LoggingwLoggerAlreadyExistsError(f"Logger '{logger_name}' already exists.")

    if not directory_path and not file_path:
        raise ValueError("You need to provide 'directory_path' or 'file_path'.")
    if directory_path and file_path:
        raise ValueError("You can't provide both 'directory_path' and 'file_path'.")

    if directory_path:
        if directory_path.endswith(os.sep):
            directory_path = directory_path[:-1]

        file_path = f"{directory_path}{os.sep}{logger_name}.{file_type}"

    logger = get_logger_with_level(logger_name, logging_level)

    if add_stream:
        handlers.add_stream_handler(
            logger=logger, logging_level=logging_level, formatter=formatter_streamhandler,
            formatter_use_nanoseconds=formatter_streamhandler_use_nanoseconds)

    if add_timedfile:
        handlers.add_timedfilehandler_with_queuehandler(
            logger=logger, file_path=file_path, logging_level=logging_level, formatter=formatter_filehandler,
            formatter_use_nanoseconds=formatter_filehandler_use_nanoseconds, file_type=file_type,
            rotate_at_rollover_time=filehandler_rotate_at_rollover_time,
            rotation_date_format=filehandler_rotation_date_format,
            rotation_callback_namer_function=filehandler_rotation_callback_namer_function,
            rotation_use_default_callback_namer_function=filehandler_rotation_use_default_namer_function,
            when=when, interval=interval, delay=delay, backupCount=backupCount, encoding=encoding, header=header)

    return logger


def get_logger_with_level(
        logger_name: str,
        logging_level="DEBUG"
) -> logging.Logger:
    """
    Function to get a logger and set logging level.

    :param logger_name: Name of the logger.
    :param logging_level: 'int' or 'str', Logging level to set to the logger.
        None: if None, the logger level will not be set.
    :return: Logger.
    """

    # Get the logger.
    logger: logging.Logger = loggers.get_logger(logger_name)
    # Set the logger level if it is not None.
    if logging_level:
        loggers.set_logging_level(logger, logging_level)

    return logger


def disable_default_logger():
    """
    Function to disable default logger.
    """

    # # Get the default logger.
    # logger = logging.getLogger()
    # # Remove all handlers from the logger.
    # logger.handlers.clear()
    # # Set the logger level to 'NOTSET'.
    # logger.setLevel(logging.NOTSET)
    # # Disable propagation from the 'root' logger, so we will not see the messages twice.
    # loggers.set_propagation(logger)

    # Disabling the default logger in Python
    logging.disable(logging.CRITICAL)


def get_datetime_format_string_from_logger_file_handlers(logger: logging.Logger) -> list:
    """
    Function to get datetime format string from the logger's file handlers.
    This is useful when you want to know the datetime format string that is used on file rotation.
    :param logger: Logger to get the datetime format string from.
    :return: List of datetime format strings.
    """

    datetime_format_strings = []

    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            date_time_format_string = handlers.extract_datetime_format_from_file_handler(handler)
            if date_time_format_string:
                datetime_format_strings.append(date_time_format_string)

    return datetime_format_strings


def is_logger_exists(logger_name: str) -> bool:
    """
    Function to check if the logger exists.
    :param logger_name: Name of the logger.
    :return: True if the logger exists, False if it doesn't.
    """

    return loggers.is_logger_exists(logger_name)


def find_the_parent_logger_with_stream_handler(logger: logging.Logger) -> logging.Logger:
    """
    Function to find the parent logger with StreamHandler.
    Example:
        logger_name = "parent.child.grandchild"
        'parent' logger has StreamHandler, but 'child' and 'grandchild' don't.
        This function will return the 'parent' logger, since both 'child' and 'grandchild' will inherit the
        StreamHandler from the 'parent' logger.

    :param logger: Logger to find the parent logger with StreamHandler.
    :return: Parent logger with StreamHandler.
    """

    # Start with current logger to see if it has a stream handler.
    current_logger = logger
    found: bool = False
    while current_logger and not current_logger.handlers:
        for handler in current_logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                found = True
                break

        if not found:
            # If the current logger doesn't have the stream handler, let's move to the parent.
            current_logger = current_logger.parent

    return current_logger


@contextlib.contextmanager
def _temporary_change_logger_stream_handler_color(logger: logging.Logger, color: str):
    """
    THIS IS ONLY FOR REFERENCE, for better result use the 'temporary_change_logger_stream_handler_emit_color' function.
    If there are several threads that use this logger, there could be a problem, since unwanted messages
    could be colored with the color of the other thread. 'temporary_change_logger_stream_handler_emit_color' is thread
    safe and will color only the messages from the current thread.

    Context manager to temporarily change the color of the logger's StreamHandler formatter.

    Example:
        with temporary_change_logger_stream_handler_color(logger, color):
            # Do something with the temporary color.
            pass
    """

    # Find the current or the topmost logger's StreamHandler.
    # Could be that it is a child logger inherits its handlers from the parent.
    logger_with_handlers = find_the_parent_logger_with_stream_handler(logger)

    found_stream_handler = None
    for handler in logger_with_handlers.handlers:
        if isinstance(handler, logging.StreamHandler):
            found_stream_handler = handler
            break

    # Save the original formatter
    original_formatter = found_stream_handler.formatter
    original_formatter_string = handlers.get_formatter_string(found_stream_handler)

    # Create a colored formatter for errors
    color_formatter = logging.Formatter(
        ansi_escape_codes.get_colors_basic_dict(color) + original_formatter_string +
        ansi_escape_codes.ColorsBasic.END)

    # thread_id = threading.get_ident()
    # color_filter = filters.ThreadColorLogFilter(color, thread_id)
    # found_stream_handler.addFilter(color_filter)
    try:
        found_stream_handler.setFormatter(color_formatter)
        yield
    finally:
        found_stream_handler.setFormatter(original_formatter)
        # found_stream_handler.removeFilter(color_filter)


# Thread-local storage to store color codes per thread
thread_local = threading.local()


@contextlib.contextmanager
def temporary_change_logger_stream_handler_emit_color(logger: logging.Logger, color: str):
    """Context manager to temporarily set the color code for log messages in the current thread."""

    # Find the current or the topmost logger's StreamHandler.
    # Could be that it is a child logger inherits its handlers from the parent.
    logger_with_handlers = find_the_parent_logger_with_stream_handler(logger)

    found_stream_handler = None
    for handler in logger_with_handlers.handlers:
        if isinstance(handler, logging.StreamHandler):
            found_stream_handler = handler
            break

    # Save the original emit method of the stream handler
    original_emit = found_stream_handler.emit

    def emit_with_color(record):
        original_msg = record.msg
        # Check if the current thread has a color code
        if getattr(thread_local, 'color', None):
            record.msg = (
                ansi_escape_codes.get_colors_basic_dict(color) + original_msg +
                ansi_escape_codes.ColorsBasic.END)
        original_emit(record)  # Call the original emit method
        record.msg = original_msg  # Restore the original message for other handlers

    # Replace the emit method with our custom method
    found_stream_handler.emit = emit_with_color

    # Set the color code in thread-local storage for this thread
    thread_local.color = color

    try:
        yield
    finally:
        # Restore the original emit method after the context manager is exited
        found_stream_handler.emit = original_emit
        # Clear the color code from thread-local storage
        thread_local.color = None


class ExceptionCsvLogger:
    def __init__(
            self,
            logger_name: str,
            directory_path: str = None,
            custom_header: str = None
    ):
        """
        Initialize the ExceptionCsvLogger object.

        :param logger_name: Name of the logger.
        :param directory_path: Directory path where the log file will be saved.
            You can leave it as None, but if the logger doesn't exist, you will get an exception.
        :param custom_header: Custom header to write to the log file.
            If None, the default header will be used: "timestamp,exception", since that what is written to the log file.
            If you want to add more columns to the csv file, you can provide a custom header:
                "custom1,custom2,custom3".
            These will be added to the default header as:
                "timestamp,custom1,custom2,custom3,exception".
        """

        if custom_header:
            self.header = f"timestamp,{custom_header},exception"
        else:
            self.header = "timestamp,exception"

        if is_logger_exists(logger_name):
            self.logger = get_logger_with_level(logger_name)
        else:
            if directory_path is None:
                raise ValueError("You need to provide 'directory_path' if the logger doesn't exist.")

            self.logger = create_logger(
                logger_name=logger_name,
                directory_path=directory_path,
                file_type="csv",
                add_timedfile=True,
                formatter_filehandler='MESSAGE',
                header=self.header)

    def write(
            self,
            message: Union[str, Exception] = None,
            custom_csv_string: str = None,
            stdout: bool = True
    ):
        """
        Write the message to the log file.

        :param message: The message to write to the log file.
            If None, the message will be retrieved from current traceback frame.
        :param custom_csv_string: Custom CSV string to add between the timestamp and the exception.
            Currently, without the 'custom_csv_string', the csv line written as "timestamp,exception" as the header.
            If you add a 'custom_csv_string', the csv line will be written as "timestamp,custom_csv_string,exception".
            Meaning, that you need to provide the 'custom_header' during the initialization of the object.
            Off course, you can use as many commas as you need in the 'custom_csv_string': "custom1,custom2,custom3".
            This need to be mirrored in the 'custom_header' as well: "custom1,custom2,custom3".
        :param stdout: If set to True, the exception will be printed to the console.
        """

        if message is None or isinstance(message, Exception):
            message = tracebacks.get_as_string()

        if custom_csv_string:
            output_csv_line: str = csvs.escape_csv_line_to_string([datetime.datetime.now(), custom_csv_string, message])
        else:
            output_csv_line: str = csvs.escape_csv_line_to_string([datetime.datetime.now(), message])

        # If the number of cells in the 'output_csv_line' doesn't match the number of cells in the 'header',
        # raise an exception.
        if (csvs.get_number_of_cells_in_string_line(output_csv_line) !=
                csvs.get_number_of_cells_in_string_line(self.header)):
            raise ValueError(
                "Number of cells in the 'output_csv_line' doesn't match the number of cells in the 'header'.")

        self.logger.info(output_csv_line)

        if stdout:
            print_api.print_api('', error_type=True, color="red", traceback_string=True)

    def get_logger(self):
        return self.logger

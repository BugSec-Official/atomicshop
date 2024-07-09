import logging
from logging.handlers import TimedRotatingFileHandler, QueueListener, QueueHandler
import re
import os


class TimedRotatingFileHandlerWithHeader(TimedRotatingFileHandler):
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


def get_stream_handler() -> logging.StreamHandler:
    """
    Function to get a StreamHandler.
    This handler that will output messages to the console.

    :return: StreamHandler.
    """

    return logging.StreamHandler()


def get_timed_rotating_file_handler(
        log_file_path: str, when: str = "midnight", interval: int = 1, delay: bool = False, encoding=None
) -> logging.handlers.TimedRotatingFileHandler:
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

    return TimedRotatingFileHandler(
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


def change_rotated_filename(file_handler: logging.Handler, file_extension: str):
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

    # Set variables that are responsible for setting TimedRotatingFileHandler filename on rotation.
    # Log files time format, need only date
    format_date_log_filename: str = "%Y_%m_%d"
    # Log file suffix.
    logfile_suffix: str = "_" + format_date_log_filename + file_extension
    # Regex object to match the TimedRotatingFileHandler file name suffix.
    # "re.escape" is used to "escape" strings in regex and use them as is.
    logfile_regex_suffix = re.compile(r"^\d{4}_\d{2}_\d{2}" + re.escape(file_extension) + r"$")

    # Changing the setting that we set above
    file_handler.suffix = logfile_suffix
    file_handler.namer = lambda name: name.replace(file_extension + ".", "") + file_extension
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

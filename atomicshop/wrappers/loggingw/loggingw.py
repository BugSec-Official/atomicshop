import logging
import os
import queue
from typing import Literal, Union

from . import loggers, handlers, formatters


def get_complex_logger(
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
            Literal[
                'MESSAGE',
                'DEFAULT'],
            None] = None,
        formatter_filehandler: Union[
            Literal[
                'MESSAGE',
                'DEFAULT',],
            None] = None,
        formatter_streamhandler_use_nanoseconds: bool = True,
        formatter_filehandler_use_nanoseconds: bool = True,
        when: str = "midnight",
        interval: int = 1,
        delay: bool = True,
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
    :param formatter_filehandler: string, Formatter to use for handler. It is template of how a message will look like.
        None: No formatter will be used.
        'DEFAULT': Default formatter will be used for each file extension:
            txt: "%(asctime)s | %(levelname)s | %(threadName)s | %(name)s | %(message)s"
            csv: "%(asctime)s,%(levelname)s,%(threadName)s,%(name)s,%(message)s"
            json: '{"time": "%(asctime)s", "level": "%(levelname)s", "thread": "%(threadName)s",
                "logger": "%(name)s", "message": "%(message)s"}'
        'MESSAGE': Formatter will be used only for the 'message' part.
    :param formatter_streamhandler_use_nanoseconds: bool, If set to True, the nanoseconds will be used
        in the formatter in case you provide 'asctime' element.
    :param formatter_filehandler_use_nanoseconds: bool, If set to True, the nanoseconds will be used
        in the formatter in case you provide 'asctime' element.
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

        error_logger = loggingw.get_complex_logger(
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

        error_logger = loggingw.get_complex_logger(
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
        add_stream_handler(
            logger=logger, logging_level=logging_level, formatter=formatter_streamhandler,
            formatter_use_nanoseconds=formatter_streamhandler_use_nanoseconds)

    if add_timedfile:
        add_timedfilehandler_with_queuehandler(
            logger=logger, file_path=file_path, logging_level=logging_level, formatter=formatter_filehandler,
            formatter_use_nanoseconds=formatter_filehandler_use_nanoseconds, file_type=file_type,
            when=when, interval=interval, delay=delay, encoding=encoding, header=header)

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


def _process_formatter_attribute(
        formatter: Union[
            Literal['DEFAULT', 'MESSAGE'],
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
            None] = None,
        formatter_use_nanoseconds: bool = False
):
    """
    Function to add StreamHandler to logger.
    Stream formatter will output messages to the console.
    """

    # Getting the StreamHandler.
    stream_handler = handlers.get_stream_handler()
    # Setting log level for the handler, that will use the logger while initiated.
    loggers.set_logging_level(stream_handler, logging_level)

    # If formatter_message_only is set to True, then formatter will be used only for the 'message' part.
    formatter = _process_formatter_attribute(formatter)

    # If formatter was provided, then it will be used.
    if formatter:
        logging_formatter = formatters.get_logging_formatter_from_string(
            formatter=formatter, use_nanoseconds=formatter_use_nanoseconds)
        handlers.set_formatter(stream_handler, logging_formatter)

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

    if file_type == "csv":
        # If file extension is CSV, we'll set the header to the file.
        # This is needed since the CSV file will be rotated, and we'll need to set the header each time.
        # We'll use the custom TimedRotatingFileHandlerWithHeader class.
        file_handler = handlers.get_timed_rotating_file_handler_with_header(
            file_path, when=when, interval=interval, delay=delay, encoding=encoding, header=header)
    else:
        file_handler = handlers.get_timed_rotating_file_handler(
            file_path, when=when, interval=interval, delay=delay, encoding=encoding)

    loggers.set_logging_level(file_handler, logging_level)

    formatter = _process_formatter_attribute(formatter, file_type=file_type)

    # If formatter was passed to the function we'll add it to handler.
    if formatter:
        # Convert string to Formatter object. Moved to newer styling of python 3: style='{'
        logging_formatter = formatters.get_logging_formatter_from_string(
            formatter=formatter, use_nanoseconds=formatter_use_nanoseconds)
        # Setting the formatter in file handler.
        handlers.set_formatter(file_handler, logging_formatter)

    # This function will change the suffix behavior of the rotated file name.
    handlers.change_rotated_filename(file_handler)

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
    handlers.start_queue_listener_for_file_handler(file_handler, queue_object)

    return handlers.get_queue_handler(queue_object)


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

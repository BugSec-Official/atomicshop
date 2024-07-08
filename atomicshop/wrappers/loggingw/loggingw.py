import os
import logging
import queue

from . import loggers, handlers, formatters


def get_logger_with_level(logger_name: str, logging_level="DEBUG") -> logging.Logger:
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


def get_logger_with_stream_handler(
        logger_name: str, logging_level="DEBUG",
        formatter: str = "%(levelname)s | %(threadName)s | %(name)s | %(message)s"
) -> logging.Logger:
    """
    Function to get a logger and add StreamHandler to it.

    :param logger_name: Name of the logger.
    :param logging_level: 'int' or 'str', Logging level to set to the logger.
        None: if None, the logger level will not be set.
    :param formatter: Formatter to use for StreamHandler. It is template of how a message will look like.
    :return: Logger.
    """

    # Get the logger.
    logger: logging.Logger = loggers.get_logger(logger_name)
    # Set the logger level if it is not None.
    if logging_level:
        loggers.set_logging_level(logger, logging_level)
    # Add StreamHandler to the logger.
    add_stream_handler(logger, logging_level, formatter)

    return logger


def get_logger_with_timedfilehandler(
        logger_name: str,
        directory_path, file_name: str = None, file_extension: str = '.txt',
        logging_level="DEBUG", formatter='default',
        formatter_message_only: bool = False, disable_duplicate_ms: bool = False,
        when: str = "midnight", interval: int = 1, delay: bool = True, encoding=None
) -> logging.Logger:
    logger = get_logger_with_level(logger_name, logging_level)
    add_timedfilehandler_with_queuehandler(
        logger, directory_path, file_name, file_extension, logging_level, formatter,
        formatter_message_only, disable_duplicate_ms, when, interval, delay, encoding
    )

    return logger


def get_logger_with_stream_handler_and_timedfilehandler(
        logger_name: str,
        directory_path,
        file_name: str = None,
        file_extension: str = '.txt',
        logging_level="DEBUG",
        formatter_filehandler='default',
        formatter_streamhandler: str = "%(levelname)s | %(threadName)s | %(name)s | %(message)s",
        formatter_message_only: bool = False,
        disable_duplicate_ms: bool = False,
        when: str = "midnight",
        interval: int = 1,
        delay: bool = True,
        encoding=None
) -> logging.Logger:
    """
    Function to get a logger and add StreamHandler and TimedRotatingFileHandler to it.

    :param logger_name: Name of the logger.
    :param directory_path: string, Path to the directory where the log file will be created.
    :param file_name: string, Name of the log file without file extension, since we add it through separate argument.
        If not provided, logger name will be used.
    :param file_extension: string, Extension of the log file. Default is '.txt'.
        '.txt': Text file.
        '.csv': CSV file.
        '.json': JSON file.
    :param logging_level: str or int, Logging level for the handler, that will use the logger while initiated.
    :param formatter_filehandler: string, Formatter to use for handler. It is template of how a message will look like.
        None: No formatter will be used.
        'default': Default formatter will be used for each file extension:
            .txt: "%(asctime)s | %(levelname)s | %(threadName)s | %(name)s | %(message)s"
            .csv: "%(asctime)s,%(levelname)s,%(threadName)s,%(name)s,%(message)s"
            .json: '{"time": "%(asctime)s", "level": "%(levelname)s", "thread": "%(threadName)s",
                "logger": "%(name)s", "message": "%(message)s"}'
    :param formatter_streamhandler: string, Formatter to use for StreamHandler. It is template of how a message will
        look like.
    :param formatter_message_only: bool, If set to True, formatter will be used only for the 'message' part.
    :param disable_duplicate_ms: bool, If set to True, duplicate milliseconds will be removed from formatter
        'asctime' element.
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

    :return: Logger.

    ================================================================================================================

    Working example to write CSV logs to the file and output messages to the console:
    from atomicshop.wrappers.loggingw import loggingw


    def main():
        def output_csv_header():
            # Since there is no implementation of header in logging file handler modules, we'll do it manually each time.
            header: list = ['time',
                           'host',
                           'path',
                           'error'
                           ]
            error_logger.info(','.join(header))


        output_directory: str = "D:\\logs"

        error_logger = loggingw.get_logger_with_stream_handler_and_timedfilehandler(
            logger_name="errors", directory_path=output_directory,
            file_extension=".csv", formatter_message_only=True
        )

        output_csv_header()

        error_logger.info(f"{datetime.now()},host1,/path/to/file,error message")


    if __name__ == "__main__":
        main()
    """
    logger = get_logger_with_level(logger_name, logging_level)
    add_stream_handler(logger, logging_level, formatter_streamhandler, formatter_message_only)
    add_timedfilehandler_with_queuehandler(
        logger, directory_path, file_name, file_extension, logging_level, formatter_filehandler,
        formatter_message_only, disable_duplicate_ms, when, interval, delay, encoding
    )

    return logger


def add_stream_handler(
        logger: logging.Logger, logging_level: str = "DEBUG",
        formatter: str = "%(levelname)s | %(threadName)s | %(name)s | %(message)s",
        formatter_message_only: bool = False
):
    """
    Function to add StreamHandler to logger.
    Stream formatter will output messages to the console.

    :param logger: Logger to add the handler to.
    :param logging_level: Logging level for the handler, that will use the logger while initiated.
    :param formatter: Formatter to use for StreamHandler. It is template of how a message will look like.
        None: No formatter will be used.
        'default': Default formatter will be used:
            "%(levelname)s | %(threadName)s | %(name)s | %(message)s"
    :param formatter_message_only: bool, If set to True, formatter will be used only for the 'message' part.
    """

    # Getting the StreamHandler.
    stream_handler = handlers.get_stream_handler()
    # Setting log level for the handler, that will use the logger while initiated.
    loggers.set_logging_level(stream_handler, logging_level)

    # If formatter_message_only is set to True, then formatter will be used only for the 'message' part.
    if formatter_message_only:
        formatter = "%(message)s"

    # If formatter was provided, then it will be used.
    if formatter:
        logging_formatter = formatters.get_logging_formatter_from_string(formatter)
        handlers.set_formatter(stream_handler, logging_formatter)

    # Adding the handler to the main logger
    loggers.add_handler(logger, stream_handler)

    # Disable propagation from the 'root' logger, so we will not see the messages twice.
    loggers.set_propagation(logger)


def add_timedfilehandler_with_queuehandler(
        logger: logging.Logger, directory_path, file_name_no_extension: str = None, file_extension: str = '.txt',
        logging_level="DEBUG",
        formatter='default', formatter_message_only: bool = False, disable_duplicate_ms: bool = False,
        when: str = 'midnight', interval: int = 1, delay: bool = True, encoding=None):
    """
    Function to add TimedRotatingFileHandler and QueueHandler to logger.
    TimedRotatingFileHandler will output messages to the file through QueueHandler.
    This is needed, since TimedRotatingFileHandler is not thread-safe, though official docs say it is.

    :param logger: Logger to add the handler to.
    :param directory_path: string, Path to the directory where the log file will be created.
    :param file_name_no_extension: string, Name of the log file without file extension, since we add it through
        separate argument. If not provided, logger name will be used.
    :param file_extension: string, Extension of the log file. Default is '.txt'.
    :param logging_level: str or int, Logging level for the handler, that will use the logger while initiated.
    :param formatter: string, Formatter to use for handler. It is template of how a message will look like.
        None: No formatter will be used.
        'default': Default formatter will be used for each file extension:
            .txt: "%(asctime)s | %(levelname)s | %(threadName)s | %(name)s | %(message)s"
            .csv: "%(asctime)s,%(levelname)s,%(threadName)s,%(name)s,%(message)s"
            .json: '{"time": "%(asctime)s", "level": "%(levelname)s", "thread": "%(threadName)s",
                "logger": "%(name)s", "message": "%(message)s"}'
    :param formatter_message_only: bool, If set to True, formatter will be used only for the 'message' part.
    :param disable_duplicate_ms: bool, If set to True, duplicate milliseconds will be removed from formatter
        'asctime' element.
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
    """

    # If file name wasn't provided we will use the logger name instead.
    if not file_name_no_extension:
        file_name_no_extension = logger.name

    # Set log file path.
    log_file_path = f'{directory_path}{os.sep}{file_name_no_extension}{file_extension}'

    # Setting the TimedRotatingFileHandler, without adding it to the logger.
    # It will be added to the QueueListener, which will use the TimedRotatingFileHandler to write logs.
    # This is needed since there's a bug in TimedRotatingFileHandler, which won't let it be used with
    # threads the same way it would be used for multiprocess.

    # Creating file handler with log filename. At this stage the log file is created and locked by the handler,
    # Unless we use "delay=True" to tell the class to write the file only if there's something to write.
    file_handler = handlers.get_timed_rotating_file_handler(
        log_file_path, when=when, interval=interval, delay=delay, encoding=encoding)
    loggers.set_logging_level(file_handler, logging_level)

    if formatter == "default":
        # Create file formatter based on extension
        if file_extension == ".txt":
            formatter = formatters.DEFAULT_FORMATTER_TXT_FILE
        elif file_extension == ".csv":
            formatter = formatters.DEFAULT_FORMATTER_CSV_FILE
        elif file_extension == ".json":
            formatter = "%(message)s"

    # If 'formatter_message_only' is set to 'True', we'll use the formatter only for the message part.
    if formatter_message_only:
        formatter = "%(message)s"

    # If formatter was passed to the function we'll add it to handler.
    if formatter:
        # Convert string to Formatter object. Moved to newer styling of python 3: style='{'
        logging_formatter = formatters.get_logging_formatter_from_string(
            formatter, disable_duplicate_ms=disable_duplicate_ms)
        # Setting the formatter in file handler.
        handlers.set_formatter(file_handler, logging_formatter)

    # This function will change the suffix behavior of the rotated file name.
    handlers.change_rotated_filename(file_handler, file_extension)

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

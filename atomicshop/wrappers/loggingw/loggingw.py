import logging
import os
from typing import Literal, Union

from . import loggers, handlers


# noinspection PyPep8Naming
def create_logger(
        logger_name: str,
        get_existing_if_exists: bool = True,
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
    :param get_existing_if_exists: bool, If set to True, the logger will be returned if it already exists.
        If set to False, the new stream/file handler will be added to existing logger again.
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

    if not directory_path and not file_path:
        raise ValueError("You need to provide 'directory_path' or 'file_path'.")
    if directory_path and file_path:
        raise ValueError("You can't provide both 'directory_path' and 'file_path'.")

    if directory_path:
        if directory_path.endswith(os.sep):
            directory_path = directory_path[:-1]

        file_path = f"{directory_path}{os.sep}{logger_name}.{file_type}"

    # Check if the logger exists before creating it/getting the existing.
    is_logger_exists = loggers.is_logger_exists(logger_name)

    logger = get_logger_with_level(logger_name, logging_level)

    # If the logger already exists, and we don't want to add the handlers again, return the logger.
    if get_existing_if_exists and is_logger_exists:
        return logger

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

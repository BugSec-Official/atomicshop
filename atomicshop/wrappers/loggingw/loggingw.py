import logging
import os
from logging import Logger
from logging.handlers import QueueListener
from typing import Literal, Union
import datetime
import contextlib
import threading
import queue
import multiprocessing
import time

from . import loggers, handlers, filters
from ...file_io import csvs
from ...basics import tracebacks, ansi_escape_codes
from ... import print_api


QUEUE_LISTENER_PROCESS_NAME_PREFIX: str = "QueueListener-"


class LoggingwLoggerAlreadyExistsError(Exception):
    pass


# noinspection PyPep8Naming
def create_logger(
        logger_name: str = None,
        get_queue_listener: bool = False,
        start_queue_listener_multiprocess_add_queue_handler: bool = False,

        add_stream: bool = False,
        add_timedfile: bool = False,
        add_timedfile_with_internal_queue: bool = False,
        add_queue_handler: bool = False,

        log_queue: Union[queue.Queue, multiprocessing.Queue] = None,
        file_path: str = None,
        directory_path: str = None,
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
) -> None | QueueListener | Logger:
    """
    Function to get a logger and add StreamHandler and TimedRotatingFileHandler to it.

    :param logger_name: Name of the logger.
    :param get_queue_listener: bool, If set to True, QueueListener will be started with all the handlers
        like 'add_timedfile' and 'add_stream', using the 'log_queue'.
    :param start_queue_listener_multiprocess_add_queue_handler: bool, If set to True, the QueueListener will be
        started in a separate multiprocessing process, without you handling this manually.

    Only one of the following parameters can be set at a time: 'logger_name', 'get_queue_listener'.

    :param file_path: full path to the log file. If you don't want to use the file, set it to None.
        You can set the directory_path only and then the 'logger_name' will be used as the file name with the
        'file_type' as the file extension.
    :param directory_path: full path to the directory where the log file will be saved.
    :param add_stream: bool, If set to True, StreamHandler will be added to the logger.
    :param add_timedfile: bool, If set to True, TimedRotatingFileHandler will be added to the logger directly.
    :param add_timedfile_with_internal_queue: bool, If set to True, TimedRotatingFileHandler will be added
        to the logger, but not directly.
        Internal queue.Queue will be created, then used by the QueueListener, which will get the
        TimerRotatingFileHandler as the handler.
        Then the QueueHandler using the same internal queue will be added to the logger.
        This is done to improve the multithreading compatibility.
    :param add_queue_handler: bool, If set to True, QueueHandler will be added to the logger, using the 'log_queue'.
    :param log_queue: queue.Queue or multiprocessing.Queue, Queue to use for the QueueHandler.
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
            add_timedfile_with_internal_queue=True,
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
            add_timedfile_with_internal_queue=True,
            file_type='txt',
            formatter_streamhandler='DEFAULT',
            formatter_filehandler='DEFAULT'
        )

        error_logger.info(f"{datetime.now()},host1,/path/to/file,error message")


    if __name__ == "__main__":
        main()

    ------------------------------

    Example to use StreamHandler to output to console and TimedRotatingFileHandler to write to file in multiprocessing,
    while QueueListener is in the main process writes to the file and outputs to the console and the QueueHandler
    in two child subprocesses sends the logs to the main process through the multiprocessing.Queue:

    import sys
    import multiprocessing
    from atomicshop.wrappers.loggingw import loggingw


    def worker1(
        log_queue: multiprocessing.Queue,
        logger_name: str
    ):
        error_logger = loggingw.create_logger(
            logger_name=logger_name,
            add_queue_handler=True,
            log_queue=log_queue
        )

        error_logger.info("Worker1 log message for 'network' logger.")


    def worker2(
        log_queue: multiprocessing.Queue,
        logger_name: str
    ):
        error_logger = loggingw.create_logger(
            logger_name=logger_name,
            add_queue_handler=True,
            log_queue=log_queue
        )

        error_logger.info("Worker2 log message for 'network' logger.")


    def main():
        log_queue = multiprocessing.Queue()

        queue_listener = loggingw.create_logger(
            get_queue_listener=True,
            add_stream=True,
            add_timedfile=True,
            log_queue=log_queue,
            file_type='txt',
            formatter_streamhandler='DEFAULT',
            formatter_filehandler='DEFAULT'
        )

        process1 = multiprocessing.Process(target=worker1, args=(log_queue, 'network'))
        process2 = multiprocessing.Process(target=worker2, args=(log_queue, 'network'))

        process1.start()
        process2.start()

        process1.join()
        process2.join()

        # If we exit the function, we need to stop the listener
        queue_listener.stop()

        return 0


    if __name__ == "__main__":
        sys.exit(main())

    --------------------------------------------------

    Example if you need to start a QueueListener in multiprocessing, which is less garbage code and python's
    garbage collector handles the listener closing without the need to call 'stop()' method:

    import sys
    import multiprocessing
    from atomicshop.wrappers.loggingw import loggingw


    def worker1(
        log_queue: multiprocessing.Queue,
        logger_name: str
    ):
        error_logger = loggingw.create_logger(
            logger_name=logger_name,
            add_queue_handler=True,
            log_queue=log_queue
        )

        error_logger.info("Worker1 log message for 'network' logger.")


    def worker2(
        log_queue: multiprocessing.Queue,
        logger_name: str
    ):
        error_logger = loggingw.create_logger(
            logger_name=logger_name,
            add_queue_handler=True,
            log_queue=log_queue
        )

        error_logger.info("Worker2 log message for 'network' logger.")


    def main():
        log_queue = multiprocessing.Queue()
        logger_name: str = 'network'

        loggingw.start_queue_listener_in_multiprocessing(
            logger_name=logger_name,
            add_stream=True,
            add_timedfile=True,
            log_queue=log_queue,
            file_type='txt',
            formatter_streamhandler='DEFAULT',
            formatter_filehandler='DEFAULT'
        )

        # If you want you can get the QueueListener processes.
        # listener_processes = loggingw.get_listener_processes(logger_name=logger_name)[0]
        # Or if you started several listeners, you can get all of them:
        # listener_processes_list: list = loggingw.get_listener_processes()

        process1 = multiprocessing.Process(target=worker1, args=(log_queue, logger_name))
        process2 = multiprocessing.Process(target=worker2, args=(log_queue, logger_name))

        process1.start()
        process2.start()

        process1.join()
        process2.join()

        return 0


    if __name__ == "__main__":
        sys.exit(main())

    ---------------------------------------------------

    Or you can use the 'create_logger' function with 'start_queue_listener_multiprocess=True' parameter,
    which will start the QueueListener in a separate multiprocessing process automatically if you want to use the
    queue handler logger also in the main process:

    import sys
    import multiprocessing
    from atomicshop.wrappers.loggingw import loggingw


    def worker1(
        log_queue: multiprocessing.Queue,
        logger_name: str
    ):
        error_logger = loggingw.create_logger(
            logger_name=logger_name,
            add_queue_handler=True,
            log_queue=log_queue
        )

        error_logger.info("Worker1 log message for 'network' logger.")


    def worker2(
        log_queue: multiprocessing.Queue,
        logger_name: str
    ):
        error_logger = loggingw.create_logger(
            logger_name=logger_name,
            add_queue_handler=True,
            log_queue=log_queue
        )

        error_logger.info("Worker2 log message for 'network' logger.")


    def main():
        log_queue = multiprocessing.Queue()

        main_logger: Logger = loggingw.create_logger(
            logger_name='network',
            start_queue_listener_multiprocess_add_queue_handler=True,
            add_stream=True,
            add_timedfile=True,
            log_queue=log_queue,
            file_type='txt',
            formatter_streamhandler='DEFAULT',
            formatter_filehandler='DEFAULT'
        )

        main_logger.info("Main process log message for 'network' logger.")

        # If you want you can get the QueueListener processes.
        # listener_processes = loggingw.get_listener_processes(logger_name=logger_name)[0]
        # Or if you started several listeners, you can get all of them:
        # listener_processes_list: list = loggingw.get_listener_processes()

        process1 = multiprocessing.Process(target=worker1, args=(log_queue, 'network'))
        process2 = multiprocessing.Process(target=worker2, args=(log_queue, 'network'))

        process1.start()
        process2.start()

        process1.join()
        process2.join()

        return 0


    if __name__ == "__main__":
        sys.exit(main())
    """

    if start_queue_listener_multiprocess_add_queue_handler and (get_queue_listener or add_queue_handler):
        raise ValueError("You don't need to set 'get_queue_listener' or 'add_queue_handler' "
                         "when setting 'start_queue_listener_multiprocess_add_queue_handler'.")

    if start_queue_listener_multiprocess_add_queue_handler:
        logger_instance: Logger = _create_logger_with_queue_handler(
            logger_name=logger_name,
            log_queue=log_queue
        )

        # Start the QueueListener in a separate multiprocessing process.
        start_queue_listener_in_multiprocessing(
            logger_name=logger_name,
            add_stream=add_stream,
            add_timedfile=add_timedfile,
            add_timedfile_with_internal_queue=add_timedfile_with_internal_queue,
            log_queue=log_queue,
            file_path=file_path,
            directory_path=directory_path,
            file_type=file_type,
            logging_level=logging_level,
            formatter_streamhandler=formatter_streamhandler,
            formatter_filehandler=formatter_filehandler,
            formatter_streamhandler_use_nanoseconds=formatter_streamhandler_use_nanoseconds,
            formatter_filehandler_use_nanoseconds=formatter_filehandler_use_nanoseconds,
            filehandler_rotate_at_rollover_time=filehandler_rotate_at_rollover_time,
            filehandler_rotation_date_format=filehandler_rotation_date_format,
            filehandler_rotation_callback_namer_function=filehandler_rotation_callback_namer_function,
            filehandler_rotation_use_default_namer_function=filehandler_rotation_use_default_namer_function,
            when=when,
            interval=interval,
            backupCount=backupCount,
            delay=delay,
            encoding=encoding,
            header=header
        )

        return logger_instance

    if logger_name and get_queue_listener and not start_queue_listener_multiprocess_add_queue_handler:
        raise ValueError("You can't set both 'logger_name' and 'get_queue_listener'.")
    if not logger_name and not get_queue_listener:
        raise ValueError("You need to provide 'logger_name' or 'get_queue_listener'.")

    # Check if the logger exists before creating it.
    if logger_name:
        if loggers.is_logger_exists(logger_name):
            raise LoggingwLoggerAlreadyExistsError(f"Logger '{logger_name}' already exists.")

    if not logger_name and not file_path:
        raise ValueError("You need to provide 'file_path' if 'logger_name' is not set.")

    if get_queue_listener and not log_queue:
        raise ValueError("You need to provide 'log_queue' if 'get_queue_listener' is set to True.")

    if add_queue_handler and not log_queue:
        raise ValueError("You need to provide 'log_queue' if 'add_queue_handler' is set to True.")

    if add_timedfile or add_timedfile_with_internal_queue:
        if not directory_path and not file_path:
            raise ValueError("You need to provide 'directory_path' or 'file_path'.")
        if directory_path and file_path:
            raise ValueError("You can't provide both 'directory_path' and 'file_path'.")

    if directory_path:
        if directory_path.endswith(os.sep):
            directory_path = directory_path[:-1]

        file_path = f"{directory_path}{os.sep}{logger_name}.{file_type}"

    # --- Add the handlers to a tuple ---

    handlers_tuple: tuple = ()
    if add_stream:
        stream_handler = handlers.get_stream_handler_extended(
            logging_level=logging_level,
            formatter=formatter_streamhandler,
            formatter_use_nanoseconds=formatter_streamhandler_use_nanoseconds)

        handlers_tuple += (stream_handler,)

    if add_timedfile:
        timed_file_handler = handlers.get_timed_rotating_file_handler_extended(
            file_path=file_path,
            logging_level=logging_level,
            formatter=formatter_filehandler,
            formatter_use_nanoseconds=formatter_filehandler_use_nanoseconds,
            file_type=file_type,
            rotate_at_rollover_time=filehandler_rotate_at_rollover_time,
            rotation_date_format=filehandler_rotation_date_format,
            rotation_callback_namer_function=filehandler_rotation_callback_namer_function,
            rotation_use_default_callback_namer_function=filehandler_rotation_use_default_namer_function,
            when=when,
            interval=interval,
            delay=delay,
            backupCount=backupCount,
            encoding=encoding,
            header=header
        )

        handlers_tuple += (timed_file_handler,)

    if add_timedfile_with_internal_queue:
        timed_file_handler_with_queue = handlers.get_timed_rotating_file_handler_extended(
            file_path=file_path,
            logging_level=logging_level,
            formatter=formatter_filehandler,
            formatter_use_nanoseconds=formatter_filehandler_use_nanoseconds,
            file_type=file_type,
            rotate_at_rollover_time=filehandler_rotate_at_rollover_time,
            rotation_date_format=filehandler_rotation_date_format,
            rotation_callback_namer_function=filehandler_rotation_callback_namer_function,
            rotation_use_default_callback_namer_function=filehandler_rotation_use_default_namer_function,
            use_internal_queue_listener=True,
            when=when,
            interval=interval,
            delay=delay,
            backupCount=backupCount,
            encoding=encoding,
            header=header
        )

        handlers_tuple += (timed_file_handler_with_queue,)

    if add_queue_handler:
        queue_handler = handlers.get_queue_handler_extended(log_queue)
        handlers_tuple += (queue_handler,)

    # --- Create the logger ---

    if logger_name:
        logger = get_logger_with_level(logger_name, logging_level)

        # Add the handlers to the logger.
        for handler in handlers_tuple:
            loggers.add_handler(logger, handler)

        # Disable propagation from the 'root' logger, so we will not see the messages twice.
        loggers.set_propagation(logger)

        return logger

    # --- create the QueueListener ---

    if get_queue_listener:
        queue_listener: logging.handlers.QueueListener = handlers.start_queue_listener_for_handlers(handlers_tuple, log_queue)
        return queue_listener


def _create_logger_with_queue_handler(
            logger_name: str,
            log_queue: Union[queue.Queue, multiprocessing.Queue]
    ) -> Logger:
    """
    The function to create a logger with QueueHandler so the QueueListener can be started later in multiprocessing.
    """

    logger_instance: Logger = create_logger(
        logger_name=logger_name,
        add_queue_handler=True,
        log_queue=log_queue
    )

    return logger_instance


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


def start_queue_listener_in_multiprocessing(
        logger_name: str = None,

        add_stream: bool = False,
        add_timedfile: bool = False,
        add_timedfile_with_internal_queue: bool = False,

        log_queue: Union[queue.Queue, multiprocessing.Queue] = None,
        file_path: str = None,
        directory_path: str = None,
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
) -> multiprocessing.Process:
    """
    Function to start a QueueListener in multiprocessing.
    PARAMETERS are same as in 'create_logger' function.

    logger_name: Name of the logger. Will be used only to name the QueueListener process.
    """

    if not file_path and directory_path and logger_name:
        file_path = f"{directory_path}{os.sep}{logger_name}.{file_type}"

    worker_kwargs = dict(
        get_queue_listener=True,

        add_stream=add_stream,
        add_timedfile=add_timedfile,
        add_timedfile_with_internal_queue=add_timedfile_with_internal_queue,

        log_queue=log_queue,
        file_path=file_path,
        file_type=file_type,
        logging_level=logging_level,
        formatter_streamhandler=formatter_streamhandler,
        formatter_filehandler=formatter_filehandler,
        formatter_streamhandler_use_nanoseconds=formatter_streamhandler_use_nanoseconds,
        formatter_filehandler_use_nanoseconds=formatter_filehandler_use_nanoseconds,
        filehandler_rotate_at_rollover_time=filehandler_rotate_at_rollover_time,
        filehandler_rotation_date_format=filehandler_rotation_date_format,
        filehandler_rotation_callback_namer_function=filehandler_rotation_callback_namer_function,
        filehandler_rotation_use_default_namer_function=filehandler_rotation_use_default_namer_function,
        when=when,
        interval=interval,
        backupCount=backupCount,
        delay=delay,
        encoding=encoding,
        header=header,
    )

    is_ready: multiprocessing.Event = multiprocessing.Event()

    # Create a new process to run the QueueListener.
    queue_listener_process = multiprocessing.Process(
        target=_queue_listener_multiprocessing_worker,
        name=f"{QUEUE_LISTENER_PROCESS_NAME_PREFIX}{logger_name}",
        args=(is_ready,),
        kwargs=worker_kwargs,
        daemon=True
    )
    queue_listener_process.start()

    # Wait until the QueueListener is loaded and ready.
    is_ready.wait()

    return queue_listener_process


def _queue_listener_multiprocessing_worker(
        is_ready: multiprocessing.Event,
        **kwargs
):
    network_logger_queue_listener = create_logger(**kwargs)
    is_ready.set()  # Signal that the logger is loaded and ready.

    try:
        while True:
            time.sleep(1)  # keep the process alive
    except KeyboardInterrupt:
        pass
    finally:
        network_logger_queue_listener.stop()


def get_listener_processes(
        logger_name: str = None
) -> list:
    """
    Function to get the list of QueueListener processes.
    :param logger_name: Name of the logger to filter the listener processes.
        If None, all listener processes will be returned.
        If provided logger_name, only the listener processes for that logger will be returned.
    :return: List of QueueListener multiprocessing processes.
    """

    listener_processes: list = []
    for process in multiprocessing.active_children():
        # If logger_name is provided, filter the processes by logger_name.
        if logger_name and process.name == f"{QUEUE_LISTENER_PROCESS_NAME_PREFIX}{logger_name}":
            listener_processes.append(process)
        if not logger_name and process.name.startswith(QUEUE_LISTENER_PROCESS_NAME_PREFIX):
            listener_processes.append(process)

    return listener_processes


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


def find_the_parent_logger_with_stream_handler(logger: logging.Logger) -> logging.Logger | None:
    """
    Function to find the parent logger with StreamHandler.
    Example:
        logger_name = "parent.child.grandchild"
        'parent' logger has StreamHandler, but 'child' and 'grandchild' don't.
        This function will return the 'parent' logger, since both 'child' and 'grandchild' will inherit the
        StreamHandler from the 'parent' logger.

    :param logger: Logger to find the parent logger with StreamHandler.
    :return: Parent logger with StreamHandler or None if the logger doesn't have StreamHandler.
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

            # If none of the parent loggers have the stream handler, break the loop.
            if current_logger is None:
                break

    return current_logger


@contextlib.contextmanager
def _temporary_change_logger_stream_handler_color(logger: logging.Logger, color: str):
    """
    THIS IS ONLY FOR REFERENCE.
    Better use 'temporary_change_logger_stream_record_color', since it is thread safe.
    If there are several threads that use this logger, there could be a problem, since unwanted messages
    could be colored with the color of the other thread.

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


@contextlib.contextmanager
def temporary_change_logger_stream_record_color(logger: logging.Logger, color: str):
    """
    This function will temporarily change the color of the logger's StreamHandler record message.

    Example:
        with temporary_change_logger_stream_record_color(logger, "red"):
            # Do something with the temporary color.
            logger.error("This message will be colored with the 'red'.")
    """

    # Find the current or the topmost logger's StreamHandler.
    # Could be that it is a child logger inherits its handlers from the parent.
    logger_with_handlers = find_the_parent_logger_with_stream_handler(logger)

    found_stream_handler = None
    for handler in logger_with_handlers.handlers:
        if isinstance(handler, logging.StreamHandler):
            found_stream_handler = handler
            break

    # Save the original state of the handler
    # original_filters = found_stream_handler.filters.copy()  # To restore the original filters

    # Create a thread-specific color filter
    thread_id = threading.get_ident()
    color_filter = filters.ThreadColorLogFilter(color, thread_id)

    # Add the filter to the handler
    found_stream_handler.addFilter(color_filter)

    try:
        yield  # Do the logging within the context
    finally:
        # Restore the original filters, ensuring thread safety
        found_stream_handler.removeFilter(color_filter)


class CsvLogger:
    def __init__(
            self,
            logger_name: str,
            directory_path: str = None,
            custom_header: str = None,
            log_queue: Union[queue.Queue, multiprocessing.Queue] = None,
            add_queue_handler_start_listener_multiprocessing: bool = False,
            add_queue_handler_no_listener_multiprocessing: bool = False
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
        :param log_queue: Queue to use for the logger, needed for the queue handler/listener.

        :param add_queue_handler_start_listener_multiprocessing: bool, whether to add a queue handler that will use
            the 'log_queue' and start the queue listener with the same 'log_queue' for multiprocessing.
        :param add_queue_handler_no_listener_multiprocessing: bool, whether to add a queue handler that will use
            the 'log_queue' but will not start the queue listener for multiprocessing. This is useful when you
            already started the queue listener and want to add more handlers to the logger without
            starting a new listener.

        If you don't set any of 'add_queue_handler_start_listener_multiprocessing' or
        'add_queue_handler_no_listener_multiprocessing', the logger will be created without a queue handler.
        """

        if add_queue_handler_no_listener_multiprocessing and add_queue_handler_start_listener_multiprocessing:
            raise ValueError(
                "You can't set both 'add_queue_handler_start_listener_multiprocessing' and "
                "'add_queue_handler_no_listener_multiprocessing' to True."
            )

        self.header = custom_header

        if is_logger_exists(logger_name):
            self.logger = get_logger_with_level(logger_name)
        else:
            if directory_path is None:
                raise ValueError("You need to provide 'directory_path' if the logger doesn't exist.")

            if add_queue_handler_start_listener_multiprocessing:
                if not log_queue:
                    raise ValueError(
                        "You need to provide 'logger_queue' if 'add_queue_handler_start_listener_multiprocess' is set to True.")

                # Create a logger with a queue handler that starts a listener for multiprocessing.
                self.logger = create_logger(
                    logger_name=logger_name,
                    start_queue_listener_multiprocess_add_queue_handler=True,
                    log_queue=log_queue,
                    directory_path=directory_path,
                    add_timedfile=True,
                    formatter_filehandler='MESSAGE',
                    file_type='csv',
                    header=self.header
                )
            elif add_queue_handler_no_listener_multiprocessing:
                if not log_queue:
                    raise ValueError(
                        "You need to provide 'logger_queue' if 'add_queue_handler_no_listener_multiprocess' is set to True.")

                # Create a logger with a queue handler that does not start a listener for multiprocessing.
                self.logger = create_logger(
                    logger_name=logger_name,
                    add_queue_handler=True,
                    log_queue=log_queue
                )
            elif not add_queue_handler_start_listener_multiprocessing and not add_queue_handler_no_listener_multiprocessing:
                self.logger = create_logger(
                    logger_name=logger_name,
                    directory_path=directory_path,
                    file_type="csv",
                    add_timedfile=True,
                    formatter_filehandler='MESSAGE',
                    header=self.header)

    def write(
            self,
            row_of_cols: list
    ):
        """
        Write a row of columns to the log file.

        :param row_of_cols: List of columns to write to the csv log file.
        """

        output_csv_line: str = csvs.escape_csv_line_to_string(row_of_cols)

        # If the number of cells in the 'output_csv_line' doesn't match the number of cells in the 'header',
        # raise an exception.
        if (csvs.get_number_of_cells_in_string_line(output_csv_line) !=
                csvs.get_number_of_cells_in_string_line(self.header)):
            raise ValueError(
                "Number of cells in the 'output_csv_line' doesn't match the number of cells in the 'header'.")

        self.logger.info(output_csv_line)

    def get_logger(self):
        return self.logger


class ExceptionCsvLogger(CsvLogger):
    def __init__(
            self,
            logger_name: str,
            directory_path: str = None,
            custom_header: str = None,
            log_queue: Union[queue.Queue, multiprocessing.Queue] = None,
            add_queue_handler_start_listener_multiprocessing: bool = False,
            add_queue_handler_no_listener_multiprocessing: bool = False
    ):
        """
        Initialize the ExceptionCsvLogger object.
        """

        if custom_header:
            custom_header = f"timestamp,{custom_header},exception"
        else:
            custom_header = "timestamp,exception"

        super().__init__(
            logger_name=logger_name,
            directory_path=directory_path,
            custom_header=custom_header,
            log_queue=log_queue,
            add_queue_handler_start_listener_multiprocessing=add_queue_handler_start_listener_multiprocessing,
            add_queue_handler_no_listener_multiprocessing=add_queue_handler_no_listener_multiprocessing
        )


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
            row_of_cols: list = [datetime.datetime.now(), custom_csv_string, message]
        else:
            row_of_cols: list = [datetime.datetime.now(), message]

        super().write(row_of_cols)

        if stdout:
            print_api.print_api('', error_type=True, color="red", traceback_string=True)

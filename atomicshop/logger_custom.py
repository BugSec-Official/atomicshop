# v1.0.1 - 26.03.2023 23:50
import os
import sys
# Handle traceback extraction
import traceback
# Handle regex for TimedRotatingFileHandler suffix
import re
# Handle all the logging
import logging
# Import custom handlers from the logging module
from logging.handlers import QueueListener, QueueHandler, TimedRotatingFileHandler
# Needed for queue management object
import queue


def traceback_oneliner():
    # You can't do "traceback.format_exception(exception_object)" directly, since it expects 3 parameters and not 1,
    # even though it's a tuple of 3 objects.
    # So, splitting the exception, then using each variable in the function is an option:
    # exc_type, exc_value, exc_traceback = sys.exc_info()
    # full_traceback = traceback.format_exception(exc_type, exc_value, exc_traceback)
    # But we'll use "unpacking operator *" instead
    full_traceback = traceback.format_exception(*sys.exc_info())
    # Joining all the lines to one string
    oneline_full_traceback = ''.join(full_traceback)
    # If you print this there will be "\n" characters which will print each line on a new line, so we need
    # to replace them with something else
    function_result = oneline_full_traceback.replace('\n', ' | ')

    # If you want to go over each line removing "\n" characters, much slower than above
    # # Defining empty list for all the lines without "\n" string at the end.
    # traceback_lines = []
    # # Strip the "\n" string out of each line and add it to the list
    # for line in [line.rstrip('\n') for line in full_traceback]:
    #     traceback_lines.extend(line.splitlines())
    # # Returning one line string of all the lines
    # function_result = traceback_lines.__str__()

    return function_result


class CustomLogger:
    # The logger acts independently. if "logger_name" specified like "parent_logger.child_logger",
    # this logger will be used as "child_logger" of the "parent_logger".
    def __init__(self, logger_name: str, add_stream=True):
        self.logger_name: str = logger_name
        self.add_stream = add_stream
        self.logger_stacklevel: int = 3

        # Check if the logger already has handlers, though in this version it shouldn't be
        # Omitted the usage of "hasHandlers()" method, since sometimes returned "True" even when there were no handlers
        # Didn't research the issue much, just used the "len(logger.handlers)" to check how many handlers there are
        # in the logger.
        # if not logging.getLogger(function_module_name).hasHandlers():
        # if len(logging.getLogger(function_module_name).handlers) == 0:
        # The check is for reference only, not needed in this script

        # Define the logger
        self.logger = logging.getLogger(self.logger_name)
        # Setting the lowest possible level on the main logger to be able to use different types of logging
        self.logger.setLevel(logging.DEBUG)

        # If 'add_stream' was set to 'False' manually, StreamHandler won't be added to logger.
        # The default is 'True'.
        if self.add_stream:
            # If there are no handlers, then the logger wasn't initialized during the script start. In this case
            # file path and extension should be passed to initialize.
            # If the logger is a child (containing "." in the name), then no initiation is needed since the parent
            # was already initiated.
            if len(self.logger.handlers) == 0 and "." not in self.logger.name:
                self.add_stream_handler()

    def add_stream_handler(self):
        # Only Stream formatter that will output to the console
        # ".40" truncating the string to only 40 characters. Example: %(message).250s
        log_formatter_stream: str = "%(levelname)s | %(threadName)s | %(name)s | %(message)s"

        # Adding StreamHandler to the main logger of the module
        # Setting the handler that will output messages to the console
        stream_handler = logging.StreamHandler()
        # Setting log level for the handler, that will use the logger while initiated
        stream_handler.setLevel(logging.DEBUG)
        # The formatter will be used as template as to what will be streamed to the console
        stream_handler.setFormatter(logging.Formatter(log_formatter_stream))
        # Adding the handler to the main logger
        self.logger.addHandler(stream_handler)

    # noinspection GrazieInspection
    def add_timedfilehandler_with_queuehandler(self,
                                               file_extension: str = None,
                                               directory_path: str = None,
                                               file_name: str = None,
                                               formatter=None):
        # Giving more logical name.
        passed_formatter = formatter

        # If file name wasn't provided we will use the logger name instead.
        if not file_name:
            file_name = self.logger_name

        # Defining the file formatter string variable
        log_formatter_file: str = str()

        # Create file formatter based on extension
        if file_extension == ".txt":
            # All the headers for the first line of the logs
            log_header_time: str = "Event Time (Y-M-D H:M:S,MS.mS) "
            log_header_level: str = "Log Level"
            log_header_logger: str = "Logger Name                     "
            log_header_script: str = "ScriptFileName            "
            log_header_line: str = "Line "
            # This is going to be printed on the first line
            log_header_final: str = f"{log_header_time} | {log_header_level} | {log_header_logger} | " \
                                    f"{log_header_script} : {log_header_line} | Thread ID: Message"

            # Log formatter, means how the log will look inside the file
            # Format for specific object: %(levelname)s
            # Format with adding spaces after the object with maximum of 10 characters: %(levelname)-10s
            # Format with adding spaces before the object with maximum of 10 characters: %(levelname)10s
            # ".40" truncating the string to only 40 characters.
            # Adding '%(asctime)s.%(msecs)06f' will print milliseconds as well as nanoseconds:
            # 2022-02-17 15:15:51,913.335562
            # If you don't use custom 'datefmt' in your 'setFormatter' function, it will print duplicate milliseconds:
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

            log_formatter_file: str = "{asctime},{msecs:013.9f} | " \
                                      "{levelname:<" + f"{len(log_header_level)}" + "s} | " \
                                      "{name:<" + f"{len(log_header_logger)}" + "s} | " \
                                      "{filename:<" + f"{len(log_header_script)}" + "s} : " \
                                      "{lineno:<" + f"{len(log_header_line)}" + "d} | " \
                                      "{threadName} | {message}"
        elif file_extension == ".csv":
            log_formatter_file: str = \
                '\"{asctime}.{msecs:010.6f}\",{levelname},{name},{filename},{lineno},{threadName},\"{message}\"'
        elif file_extension == ".json":
            log_formatter_file: str = "%(message)s"

        # Defining log path for the logger
        function_log_filepath = directory_path + os.sep + file_name + file_extension

        # Defining variables that are going to be responsible for setting TimedRotatingFileHandler filename
        # on rotation
        # Log files time format, need only date
        format_date_log_filename: str = "%Y_%m_%d"
        # Log file suffix
        logfile_suffix: str = "_" + format_date_log_filename + file_extension
        # Regex object to match the TimedRotatingFileHandler file name suffix
        # "re.escape" is used to "escape" strings in regex and use them as is
        logfile_regex_suffix = re.compile(r"^\d{4}_\d{2}_\d{2}" + re.escape(file_extension) + r"$")

        # Setting the TimedRotatingFileHandler, without adding it to the logger.
        # It will be added to the QueueListener, which will use the TimedRotatingFileHandler to write logs.
        # This is needed since there's a bug in TimedRotatingFileHandler, which won't let it be used with
        # threads the same way it would be used for multiprocess.

        # Creating file handler with log filename. At this stage the log file is created and locked by the handler,
        # Unless we use "delay=True" to tell the class to write the file only if there's something to write.
        # when="midnight" is set to rotate the filename at midnight. This means that the current file name will be
        # added Yesterday's date to the end of the file and today's file will continue to write at the same
        # filename. Also, if the script finished working on 25.11.2021, the name of the log file will be "test.log"
        # If you run the script again on 28.11.2021, the logging module will take the last modification date of
        # the file "test.log" and assign a date to it: test.log.2021_11_25
        # The log filename of 28.11.2021 will be called "test.log" again
        # By default "mode" parameter of the class uses "a" (append) mode to the log files
        # file_handler = CustomTimedRotatingFileHandler(filename=function_log_filepath, interval=1, when="midnight",
        #                                              delay=True, header=log_header_final)

        # You don't have to set the name for the handler, only if you want
        # handler.set_name("Test Handler111")
        # You can get this name later by
        # handler.get_name()

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

        file_handler = TimedRotatingFileHandler(
            filename=function_log_filepath, interval=1, when="midnight", delay=True)
        # Setting also the lowest logging level also for the handler
        file_handler.setLevel(logging.DEBUG)

        # Adding the string format of how each line is going to be added.
        # Since we're using '%(asctime)s.%(msecs)06f' msecs value in our time stamp, we need to use custom
        # 'datefmt' to get rid of the additional duplicate milliseconds:
        # Instead of '2022-02-17 15:15:51,913.913.335562' print '2022-02-17 15:15:51,913.335562'
        # The problem with this method is that milliseconds aren't adjusted to 3 digits with zeroes (like 1 = 001)
        # this means that we needed to write 'CustomFormatter' to fix that.
        # Now we can use the regular strftime format: datefmt='%Y-%m-%d,%H:%M:%S:%f'

        # Old tryouts for reference:
        #   file_formatter = logging.Formatter(log_formatter_file, style='{')
        #   file_formatter.default_time_format = '%Y-%m-%d %H:%M:%S'
        #   file_formatter.default_msec_format = '%s,%03d'
        #   file_formatter.default_msec_format = '%s,%03f'

        # Moved to newer styling of python 3: style='{'
        # If formatter wasn't passed to the function.
        if not passed_formatter:
            # Use built formatter.
            file_formatter = logging.Formatter(log_formatter_file, style='{', datefmt='%Y-%m-%d,%H:%M:%S')
        # If formatter was passed to the function.
        else:
            # Use the passed formatter.
            file_formatter = logging.Formatter(passed_formatter, style='{', datefmt='%Y-%m-%d,%H:%M:%S')
        # Setting the formatter in file handler.
        file_handler.setFormatter(file_formatter)

        # Changing the setting that we set above
        file_handler.suffix = logfile_suffix
        file_handler.namer = lambda name: name.replace(file_extension + ".", "") + file_extension
        file_handler.extMatch = logfile_regex_suffix

        # Create the Queue between threads. "-1" means that there can infinite number of items that can be
        # put in the Queue. if integer is bigger than 0, it means that this will be the maximum
        # number of items.
        class_queue = queue.Queue(-1)

        # Create the QueueListener based on TimedRotatingFileHandler
        queue_listener = QueueListener(class_queue, file_handler)
        # Start the QueueListener. Each logger will have its own instance of the Queue
        queue_listener.start()

        queue_handler = QueueHandler(class_queue)
        queue_handler.setLevel(logging.DEBUG)

        # Now after all that add the QueueHandler to the main logger
        self.logger.addHandler(queue_handler)

    def debug(self, message):
        self.logme("debug", message)

    def info(self, message):
        self.logme("info", message)

    def info_oneliner(self, message):
        self.logme("info", str(message).replace('\n', ' | '))

    def warning(self, message):
        self.logme("warning", message)

    def error(self, message):
        self.logme("error", message)

    def critical(self, message):
        self.logme("critical", message)

    # Function that logs the message
    def logme(self, level, message):
        try:
            # Since the usage is dynamic it is equivalent to:
            # self.logger.info(str(message), stacklevel=2)

            # The default "stacklevel" is 1 - the problem starts when you "lineno" in your formatter if you're
            # logging message from a class. It will always show the same line that the calling function
            # appears in the class. If you want the line number of the caller function, you need to raise it
            # by 1 level, meaning "stacklevel=2"
            # Since this is a function inside a class that is being called by another function, we need to raise
            # The level to 3
            getattr(self.logger, level)(str(message), stacklevel=self.logger_stacklevel)
        except Exception:
            print(f"!!! Couldn't write to {self.logger.handlers} | Message: {str(message)}")
            print(sys.exc_info())
            sys.exit()

    def error_exception(self, message):
        self.logme_exception("error", message)

    def error_exception_oneliner(self, message):
        self.logme_exception_oneliner("error", message)

    def critical_exception(self, message):
        self.logme_exception("critical", message)

    def critical_exception_oneliner(self, message):
        self.logme_exception_oneliner("critical", message)

    # Function that logs the message with exception.
    def logme_exception(self, level, message):
        # If exception was raised
        if sys.exc_info()[0] is not None:
            try:
                # traceback.format_exc(2) - output only 2 latest levels of traceback. Sometimes this isn't enough
                # so better set 3, but currently at default "()".
                getattr(self.logger, level)(f"{str(message)} | Exception: {sys.exc_info()[0]}, {sys.exc_info()[1]}, "
                                            f"{traceback.format_exc()}", stacklevel=self.logger_stacklevel)
                # class_module.logger.exception(f"{str(message)}")
                # class_module.logger.error(f"{str(message)}", exc_info=(exc_type, exc_value, exc_traceback))
            except Exception:
                print(f"!!! Couldn't write to {self.logger.handlers} | Message: {str(message)}")
        # If exception wasn't raised
        else:
            self.logme(level, message)

    # Function that logs the message with exception.
    def logme_exception_oneliner(self, level, message):
        # If exception was raised
        if sys.exc_info()[0] is not None:
            try:
                getattr(self.logger, level)(f"{str(message)} | Exception: {traceback_oneliner()}",
                                            stacklevel=self.logger_stacklevel)
            except Exception:
                print(f"!!! Couldn't write to {self.logger.handlers} | Message: {str(message)}")
        # If exception wasn't raised
        else:
            self.logme(level, message)

    @staticmethod
    def logger_shutdown():
        # Shutdown the logging module for cleanup purposes
        logging.shutdown()

import logging


"""
# Since the usage is dynamic it is equivalent to:
# self.logger.info(str(message), stacklevel=2)

# The default "stacklevel" is 1 - the problem starts when you "lineno" in your formatter if you're
# logging message from a class. It will always show the same line that the calling function
# appears in the class. If you want the line number of the caller function, you need to raise it
# by 1 level, meaning "stacklevel=2"
# Since this is a function inside a class that is being called by another function, we need to raise
# The level to 3
"""


def is_logger_exists(
        logger_name: str
) -> bool:
    """
    Function to check if the logger exists.
    :param logger_name: str, Name of the logger.
    :return: bool, True if the logger exists, False otherwise.
    """
    return logger_name in logging.Logger.manager.loggerDict


def get_all_existing_loggers_names() -> list:
    """
    Function to get all existing loggers names.
    :return: list, List of all existing loggers names.
    """
    return list(logging.Logger.manager.loggerDict.keys())


def get_logger(logger_name: str) -> logging.Logger:
    """
    Function to get a logger.
    :param logger_name: Name of the logger.
    :return: Logger.
    """

    # Get the logger.
    logger: logging.Logger = logging.getLogger(logger_name)

    return logger


def set_logging_level(object_to_set, logging_level="DEBUG"):
    """
    Function to set the logging level for logger or handler.
    Logger or Handler is an instance, so it sets level inplace.

    :param object_to_set: Logger / Handler to set the level to.
    :param logging_level: 'int' or 'str', Logging level to set to the logger. Default: "DEBUG".
        Example:
        int: 'logging.DEBUG' returns '10', so you can either set 'logging_level=logging.DEBUG' or 'logging_level=10'.
        str: you can set "DEBUG" string directly, 'logging_level="DEBUG"'.
    """

    object_to_set.setLevel(logging_level)


def add_handler(logger: logging.Logger, handler: logging.Handler):
    """
    Function to add handler to logger.
    :param logger: Logger to add the handler to.
    :param handler: Handler to add to the logger.
    """

    logger.addHandler(handler)


def set_propagation(logger: logging.Logger, enable: bool = False):
    """
    Function that sets propagation from the 'root' logger.
    If 'propagation is set to 'True' all the handlers that are enabled for the 'root' logger will also output messages
    resulting in duplicate messages that will appear twice.

    :param logger: Logger to add the handler to.
    :param enable: Sets the propagation from the 'root' logger to 'True' or 'False'.
    """

    logger.propagate = enable


def logger_shutdown():
    """ Shutdown the logging module for cleanup purposes """
    logging.shutdown()

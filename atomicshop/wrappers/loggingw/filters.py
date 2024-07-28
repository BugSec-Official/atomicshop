import logging
import os


class HeaderFilter(logging.Filter):
    """
    A logging.Filter that writes a header to a log file if the file is empty (
    i.e., no log records have been written, i.e.2, on file rotation).
    """
    def __init__(self, header, baseFilename):
        super().__init__()
        self.header = header
        self.baseFilename = baseFilename
        self._write_header_if_needed()

    def _write_header_if_needed(self):
        if not os.path.exists(self.baseFilename) or os.path.getsize(self.baseFilename) == 0:
            self._write_header()

    def _write_header(self):
        if self.header:
            with open(self.baseFilename, 'a') as f:
                f.write(self.header + '\n')

    def filter(self, record):
        self._write_header_if_needed()
        return True


"""
A logging.Filter in Python's logging module is an object that provides a way to perform fine-grained 
filtering of log records. 
It allows you to control which log records are passed through and which are filtered out, 
based on specific criteria you define.

Basic Concepts of logging.Filter
Purpose: Filters are used to allow or deny log records from being processed further. 
This can be based on various criteria, such as the level of the log record, the source logger, or custom attributes.
Implementation: Filters are typically subclasses of logging.Filter, 
but they can also be any callable that accepts a log record and returns a boolean value.

How logging.Filter Works
When a log record is emitted, it is passed through any filters attached to the logger or the handler. 
If the filter returns True, the log record is processed. If the filter returns False, the log record is ignored.

Example of logging.Filter
Here’s a simple example to demonstrate the use of logging.Filter:

Create a Filter: Subclass logging.Filter and override the filter method.
import logging

class MyFilter(logging.Filter):
    def filter(self, record):
        # Example: Allow only log records with a level of WARNING or higher
        return record.levelno >= logging.WARNING

Attach the Filter to a Handler or Logger:
# Create a logger
logger = logging.getLogger('my_logger')
logger.setLevel(logging.DEBUG)

# Create a console handler
console_handler = logging.StreamHandler()

# Create an instance of the custom filter
my_filter = MyFilter()

# Add the filter to the handler
console_handler.addFilter(my_filter)

# Add the handler to the logger
logger.addHandler(console_handler)

# Log some messages
logger.debug('This is a debug message')    # Will be filtered out
logger.info('This is an info message')     # Will be filtered out
logger.warning('This is a warning message') # Will be displayed
logger.error('This is an error message')   # Will be displayed
"""

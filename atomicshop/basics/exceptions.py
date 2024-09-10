import sys

from .threads import current_thread_id


# Function to print exception
def print_exception() -> None:
    # String prefix for each log that has a critical error
    error_log_prefix: str = "!!!E:"

    thread_id = current_thread_id()

    # Extract exception "type", "value" and "traceback" separately
    exc_type, exc_value, exc_traceback = sys.exc_info()

    print(f"{error_log_prefix} Thread {thread_id}: * Details: {exc_type}, {exc_value}")


def get_exception_type_string(exception: Exception) -> str:
    """ Get exception type string """
    return type(exception).__name__

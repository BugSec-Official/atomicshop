# v1.0.3 - 28.03.2023 17:20
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

# v1.0.2 - 27.03.2023 00:20
import threading


# Getting current Thread ID as integer.
def current_thread_id():
    # Trying to get the ID of the current thread. If we're not in a thread, then we'll get "IndexError"
    try:
        # "threading.current_thread().name" returns string of "Thread-N (target)" - need to remove the " (target)" part
        # and re-set the name back for use in other functions
        threading.current_thread().name = threading.current_thread().name.split()[0]
        # Extracting only the index number and converting to integer
        thread_id: int = int(threading.current_thread().name.split("-")[1])
    # If we're not in the multithreaded thread, but in the main thread
    except IndexError:
        thread_id: str = "Main"

    return thread_id


def get_number_of_active_threads():
    return threading.active_count()

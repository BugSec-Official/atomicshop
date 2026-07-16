import threading
import queue


# Getting current Thread ID as integer.
def current_thread_id():
    # Trying to get the ID of the current thread. If we're not in a thread, then we'll get "IndexError"
    try:
        # Thread names arrive as "Thread-N (target)"; strip the " (target)" suffix
        # (re-setting it for later callers), then extract N as an integer.
        strip_current_thread_name_suffix()
        thread_id: int = int(threading.current_thread().name.split("-")[1])
    # If we're not in the multithreaded thread, but in the main thread
    except IndexError:
        thread_id: str = "Main"

    return thread_id


def get_current_thread_name():
    return threading.current_thread().name


def set_current_thread_name(name: str):
    threading.current_thread().name = name


def strip_current_thread_name_suffix():
    """Drop Python 3.10+'s auto-added ' (target)' suffix from the current thread name."""
    current = threading.current_thread()
    current.name = current.name.split()[0]


def set_current_thread_name_by_process_name():
    import multiprocessing
    current_process_name = multiprocessing.current_process().name
    threading.current_thread().name = current_process_name


def get_number_of_active_threads():
    return threading.active_count()


def thread_wrap_queue(function_reference, *args, **kwargs):
    """
    The function receives function reference and arguments, and executes the function in a thread.
    "_queue" means that a queue.put() is used to store the result of the function and queue.get() to output it.

    :param function_reference: function reference to execute.
    :param args: arguments for the function.
    :param kwargs: keyword arguments for the function.
    :return: output of the referenced function.
    """

    def threaded_function():
        queue_object.put(function_reference(*args, **kwargs))

    # Create queue object.
    queue_object = queue.Queue()

    # Create thread object.
    thread_object = threading.Thread(target=threaded_function)

    # Start thread.
    thread_object.start()
    # Wait for thread to finish.
    thread_object.join()

    return queue_object.get()

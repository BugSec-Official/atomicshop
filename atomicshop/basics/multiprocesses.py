import multiprocessing
import queue


def process_wrap_queue(function_reference, *args, **kwargs):
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
    process_object = multiprocessing.Process(target=threaded_function)

    # Start thread.
    process_object.start()
    # Wait for thread to finish.
    process_object.join()

    return queue_object.get()

import sched
import threading
import time
import queue


def periodic_task(interval, priority, function_ref, args=(), sched_object=None):
    if not sched_object:
        sched_object = sched.scheduler(time.time, time.sleep)
    function_ref(*args)
    sched_object.enter(interval, priority, periodic_task, (interval, priority, function_ref, args, sched_object))
    sched_object.run()


def threaded_periodic_task(interval, function_ref, args=(), kwargs=None, thread_name=None, daemon=True):
    """
    The function executes referenced function 'function_ref' with arguments 'args' each 'interval' in a new thread.
    The old thread is closed, each time the new is executed.

    :param interval: integer or float: the interval in seconds between function executions.
    :param function_ref: name of the referenced function to execute.
    :param args: tuple, of arguments to provide for the 'function_ref' to execute.
    :param kwargs: dictionary, of keyword arguments to provide for the 'function_ref' to execute.
    :param thread_name: the name of the thread that will be created:
        threading.Thread(target=thread_timer, name=thread_name)
        The default parameter for 'Thread' 'name' is 'None', so if you don't specify the name it works as default.
    :param daemon: bool, if True, the thread will be a daemon thread. Default is True.
        Since this is a periodic task, we don't need to wait for the thread to finish, so we can set it to True.

    :return: thread object.
    """

    # If 'kwargs' is not provided, we'll initialize it as an empty dictionary.
    if not kwargs:
        kwargs = dict()

    def thread_timer():
        nonlocal interval
        nonlocal args
        nonlocal kwargs

        # # Execute the referenced function with tuple of provided arguments.
        # function_ref(*args)
        #
        # # Convert provided interval to seconds if it's a tuple.
        # interval = convert_delta_string_to_seconds(interval)
        # # Execute the function in a new thread. The current thread is closed.
        # threading.Timer(interval, threaded_periodic_task, args=(interval, function_ref, args)).start()

        while True:
            # Execute the referenced function with tuple of provided arguments.
            function_ref(*args, **kwargs)
            # Sleep for amount of seconds.
            time.sleep(interval)

    # Start in a new thread.
    thread = threading.Thread(target=thread_timer, name=thread_name)

    if daemon:
        thread.daemon = True

    thread.start()
    return thread


class ThreadLooper:
    """
    The class will execute referenced function 'function_ref' in a thread with 'args' and 'kwargs' each 'interval'.
    """
    def __init__(self):
        self.loop_queue = queue.Queue()

    def run_loop(
            self,
            function_reference,
            args=(),
            kwargs=None,
            interval_seconds=0,
            thread_name: str = None
    ):
        """
        The function executes referenced function 'function_ref' with arguments 'args' each 'interval' in a new thread.

        :param function_reference: name of the referenced function to execute.
        :param args: tuple, of arguments to provide for the 'function_ref' to execute.
        :param kwargs: dictionary, of keyword arguments to provide for the 'function_ref' to execute.
        :param interval_seconds: integer or float: the interval in seconds between function executions.
        :param thread_name: the name of the thread that will be created.
        """

        # If 'kwargs' is not provided, we'll initialize it as an empty dictionary.
        if not kwargs:
            kwargs = dict()

        def thread_function():
            nonlocal function_reference
            nonlocal args
            nonlocal kwargs
            nonlocal interval_seconds

            while True:
                result_list = function_reference(*args, **kwargs)
                self.loop_queue.put(result_list)
                time.sleep(interval_seconds)

        thread = threading.Thread(target=thread_function, name=thread_name)
        thread.daemon = True
        thread.start()

    def emit_from_loop(self):
        """
        The function will return the next result from the queue.
        The queue is blocking, so if there is no result in the queue, the function will wait until there is one.
        This should be executed in a while loop:

        while True:
            result = thread_looper.emit_from_loop()
        """
        return self.loop_queue.get()

import sched
import threading
import time

from .datetimes import convert_delta_string_to_seconds


def periodic_task(interval, priority, function_ref, args=(), sched_object=None):
    if not sched_object:
        sched_object = sched.scheduler(time.time, time.sleep)
    function_ref(*args)
    sched_object.enter(interval, priority, periodic_task, (interval, priority, function_ref, args, sched_object))
    sched_object.run()


def threaded_periodic_task(interval, function_ref, args=(), thread_name=None):
    """
    The function executes referenced function 'function_ref' with arguments 'args' each 'interval' in a new thread.
    The old thread is closed, each time the new is executed.

    :param interval: integer or float: the interval in seconds between function executions.
    :param function_ref: name of the referenced function to execute.
    :param args: tuple, of arguments to provide for the 'function_ref' to execute.
    :param thread_name: the name of the thread that will be created:
        threading.Thread(target=thread_timer, name=thread_name).start()
        The default parameter for 'Thread' 'name' is 'None', so if you don't specify the name it works as default.
    """

    def thread_timer():
        nonlocal interval
        nonlocal args

        # # Execute the referenced function with tuple of provided arguments.
        # function_ref(*args)
        #
        # # Convert provided interval to seconds if it's a tuple.
        # interval = convert_delta_string_to_seconds(interval)
        # # Execute the function in a new thread. The current thread is closed.
        # threading.Timer(interval, threaded_periodic_task, args=(interval, function_ref, args)).start()

        while True:
            # Execute the referenced function with tuple of provided arguments.
            function_ref(*args)
            # Sleep for amount of seconds.
            time.sleep(interval)

    # Start in a new thread.
    threading.Thread(target=thread_timer, name=thread_name).start()

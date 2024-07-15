import atexit
import signal
import sys
import platform

from ..print_api import print_api


def restart_function(callable_function, *args, **kwargs):
    """
    This function will run the callable function with the given arguments and keyword arguments.
    If the function raises an exception, the function will be restarted.

    :param callable_function: The function to run.
    :param args: The arguments to pass to the function.
    :param kwargs: The keyword arguments to pass to the function.
    :return: The return value of the function.
    """
    while True:
        try:
            return callable_function(*args, **kwargs)
        except Exception as e:
            print(f"ERROR: {e}")
            continue


def run_callable_on_exit_and_signals(
        callable_function,
        print_kwargs: dict = None,
        *args,
        **kwargs
):
    """
    This function will run the callable function with the given arguments and keyword arguments.
    If the function raises an exception, the function will be restarted.

    :param callable_function: The function to run.
    :param print_kwargs: print_api kwargs.
    :param args: The arguments to pass to the function.
    :param kwargs: The keyword arguments to pass to the function.
    :return: The return value of the function.
    """
    def signal_handler(signum, frame):
        print_api(f"Signal {signum} received, exiting.", **(print_kwargs or {}))
        callable_function(*args, **kwargs)
        input("Press Enter to exit.")
        sys.exit(0)

    def exit_handler():
        print_api("Exiting.", **(print_kwargs or {}))
        callable_function(*args, **kwargs)
        input("Press Enter to exit.")
        sys.exit(0)

    signals = [signal.SIGINT, signal.SIGTERM]
    if platform.system() != 'Windows':
        signals.append(signal.SIGQUIT)
        signals.append(signal.SIGHUP)
    for sig in signals:
        signal.signal(sig, signal_handler)

    # signal.signal(signal.SIGINT, signal_handler)
    # signal.signal(signal.SIGTERM, signal_handler)
    atexit.register(exit_handler)

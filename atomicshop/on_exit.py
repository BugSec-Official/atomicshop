import atexit
import signal
import sys
import platform

import win32api
import win32con

from .print_api import print_api
from .wrappers.pywin32w import console


EXIT_HANDLER_INSTANCE = None


class ExitHandler:
    """
    This class is used to handle exit events: Closing the console, pressing 'CTRL+C', Killing the process.

    Example:
        from atomicshop import on_exit


        def clean_up_function():
            print("Cleaning up.")


        on_exit.ExitHandler(clean_up_function).register_handlers()

        # OR
        on_exit.register_exit_handler(clean_up_function)
    """
    def __init__(
            self,
            cleanup_action: callable,
            args: tuple = None,
            kwargs: dict = None
    ):
        """
        :param cleanup_action: The action to run when one of exit types is triggered.
        :param args: The arguments to pass to the cleanup action.
        :param kwargs: The keyword arguments to pass to the cleanup action.
        """

        if not callable(cleanup_action):
            raise ValueError("The 'cleanup_action' must be a callable function.")

        if args is None:
            args = tuple()

        if kwargs is None:
            kwargs = dict()

        self.cleanup_action: callable = cleanup_action
        self.args: tuple = args
        self.kwargs: dict = kwargs

        self._called: bool = False
        self._handler_hit: bool = False

    def _run_cleanup(self):
        if not self._called:
            self._called = True
            self.cleanup_action(*self.args, **self.kwargs)

    def console_handler(self, event):
        if event == win32con.CTRL_CLOSE_EVENT:

            if not self._handler_hit:
                self._handler_hit = True

                print("Console close event.")
                self._run_cleanup()

            return True
        return False

    def atexit_handler(self):
        if not self._handler_hit:
            self._handler_hit = True

            print("atexit_handler")
            self._run_cleanup()

    def signal_handler(self, signum, frame):
        if not self._handler_hit:
            self._handler_hit = True

            print_api(f"Signal {signum}")
            self._run_cleanup()
            # Exit the process gracefully
            raise SystemExit(0)

    def register_handlers(
            self,
            at_exit: bool = True,
            console_close: bool = True,
            kill_signal: bool = True
    ):
        """
        Register the exit handlers.

        :param at_exit: Register the atexit handler.
            Just remember that the atexit handler will be called right away on [Ctrl+C], meaning if you want to do
            something specifically on KeyboardInterrupt, you should handle it separately and set this parameter to False.
            Same goes for all the exceptions.
        :param console_close: Register the console close handler.
        :param kill_signal: Register the kill signal handler.
        """
        if at_exit:
            atexit.register(self.atexit_handler)
        if console_close:
            win32api.SetConsoleCtrlHandler(self.console_handler, True)
        if kill_signal:
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)


def register_exit_handler(
        clean_up_function,
        at_exit: bool = True,
        console_close: bool = True,
        kill_signal: bool = True,
        *args, **kwargs):
    """
    This function will register the exit handler to handle exit events: Closing the console, pressing 'CTRL+C',
    Killing the process.

    :param clean_up_function: The action to run when one of exit types is triggered.
    :param at_exit: Register the atexit handler.
        Just remember that the atexit handler will be called right away on [Ctrl+C], meaning if you want to do something
        specifically on KeyboardInterrupt, you should handle it separately and set this parameter to False.
        Same goes for all the exceptions.
    :param console_close: Register the console close handler.
    :param kill_signal: Register the kill signal handler.
        Same problem as with atexit handler, it will be called right away on [Ctrl+C].
    :param args: The arguments to pass to the cleanup action.
    :param kwargs: The keyword arguments to pass to the cleanup action.
    """
    global EXIT_HANDLER_INSTANCE
    EXIT_HANDLER_INSTANCE = ExitHandler(clean_up_function, args, kwargs)
    EXIT_HANDLER_INSTANCE.register_handlers(at_exit=at_exit, console_close=console_close, kill_signal=kill_signal)


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


def _ref_run_callable_on_exit_and_signals(
        callable_function,
        print_kwargs: dict = None,
        *args,
        **kwargs
):
    """
    THIS IS FOR REFERENCE ONLY.

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
        sys.exit(0)

    def exit_handler():
        print_api("Exiting.", **(print_kwargs or {}))
        callable_function(*args, **kwargs)
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

    # Register console handler for Windows.
    if platform.system() == 'Windows':
        console_handler = console.ConsoleHandler(exit_handler, args, kwargs)
        console_handler.register_handler()

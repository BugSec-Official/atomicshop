import sys
import contextlib
import io
import logging


class TempDisableOutput:
    """
    The class was built to use with 'with' statement in order to temporarily disable output to console for function
    executions that their output can not be disabled.

    Usage:
        from atomicshop.console_output import TempDisableOutput
        with TempDisableOutput():
            print('test')

    If you don't want to use this function, you can use 'contextlib.redirect_stdout()' directly:
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            print('test')

    If you don't want to use it with 'with' statement, you can call '__enter__()' and '__exit__()' methods directly:
        import contextlib
        import io
        import sys
        test = contextlib.redirect_stdout(io.StringIO())
        test.__enter__()
        print('test')
        # '__exit__' method gets the 3 arguments of exception object, thus passing the exception parameters
        # if it occurs.
        test.__exit__(*sys.exc_info())
    """
    def __init__(self):
        self.redirect_stdout_object = contextlib.redirect_stdout(io.StringIO())

    def __enter__(self):
        return self.redirect_stdout_object.__enter__()

    def __exit__(self, *args):
        return self.redirect_stdout_object.__exit__(*args)


def capture_console_output_without_outputting(func, *args, **kwargs):
    """
    Executes a function and captures its console output.

    Args:
        func: The function to execute.
        *args: Arguments to pass to the function.
        **kwargs: Keyword arguments to pass to the function.

    Returns:
        A string containing the captured console output.

    Usage:
        def example_function(name):
            print(f"Hello, {name}!")

        captured_output = capture_console_output(example_function, "World")
        print("Captured output:", captured_output)

    """

    output_capture = io.StringIO()
    with contextlib.redirect_stdout(output_capture):
        func(*args, **kwargs)
    return output_capture.getvalue()


def capture_console_output_of_logging_without_outputting(func, *args, **kwargs):
    """
    Executes a function and captures its logger output.

    Args:
        func: The function to execute.
        *args: Arguments to pass to the function.
        **kwargs: Keyword arguments to pass to the function.

    Returns:
        A string containing the captured console output.

    Usage:
        def example_function():
            logger = logging.getLogger()
            logger.warning("This is a warning!")

        captured_output = capture_logger_output(example_function)
        print("Captured output:", captured_output)

    """

    log_capture_string = io.StringIO()
    ch = logging.StreamHandler(log_capture_string)
    ch.setLevel(logging.DEBUG)

    logger = logging.getLogger()
    old_handlers = logger.handlers
    logger.handlers = [ch]

    try:
        func(*args, **kwargs)
    finally:
        logger.handlers = old_handlers
        ch.close()

    return log_capture_string.getvalue()


def capture_all_output(func, *args, **kwargs):
    """
    Executes a function and captures its console and logger output.

    Args:
        func: The function to execute.
        *args: Arguments to pass to the function.
        **kwargs: Keyword arguments to pass to the function.

    Returns:
        A string containing the captured console and logger output.

    Usage:
        def example_function():
            print("This is a print statement.")
            logging.warning("This is a warning from logging.")
            sys.stderr.write("This is a direct stderr write.\n")

        captured_output = capture_all_output(example_function)
        print("Captured output:", captured_output)
    """

    log_capture_string = io.StringIO()
    ch = logging.StreamHandler(log_capture_string)
    ch.setLevel(logging.DEBUG)

    logger = logging.getLogger()
    old_handlers = logger.handlers
    logger.handlers = [ch]

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = stdout_capture
    sys.stderr = stderr_capture

    try:
        func(*args, **kwargs)
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        logger.handlers = old_handlers
        ch.close()

    return stdout_capture.getvalue() + stderr_capture.getvalue() + log_capture_string.getvalue()

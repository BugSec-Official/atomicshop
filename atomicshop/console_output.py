import contextlib
import io


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

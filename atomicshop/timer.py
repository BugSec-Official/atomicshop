import time


class TimerError(Exception):
    """A custom exception used to report errors in use of Timer class"""


class Timer:
    """ Custom timer class to measure elapsed time. Returns time in seconds (float) or nanoseconds with setting. """
    def __init__(self, nanoseconds: bool = False):
        """
        Set up timer in seconds or nanoseconds
        Seconds are returned as float, nanoseconds as int.

        :param nanoseconds: True to measure time in nanoseconds, False to measure time in seconds (default).
        """
        self._start_time = None
        self._nanoseconds: bool = nanoseconds

    def start(self):
        """Start a new timer"""

        if self._start_time is not None:
            raise TimerError(f"Timer is running. Use .stop() to stop it")

        if self._nanoseconds:
            self._start_time = time.perf_counter_ns()
        else:
            self._start_time = time.perf_counter()

    def restart(self):
        """Reset the timer"""

        self._start_time = None
        self.start()

    def measure(self):
        """Measure the elapsed time"""

        if self._start_time is None:
            raise TimerError(f"Timer is not running. Use .start() to start it")

        if self._nanoseconds:
            elapsed_time = time.perf_counter_ns() - self._start_time
        else:
            elapsed_time = time.perf_counter() - self._start_time

        return elapsed_time

    def stop(self):
        """Stop the timer, and report the elapsed time"""

        elapsed_time = self.measure()
        self._start_time = None

        return elapsed_time

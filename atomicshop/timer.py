import time


class TimerError(Exception):
    """A custom exception used to report errors in use of Timer class"""


class Timer:
    """ Custom timer class to measure elapsed time. Returns time in seconds (float) or nanoseconds with setting. """
    def __init__(
            self,
            nanoseconds: bool = False
    ):
        """
        Set up timer in seconds or nanoseconds
        Seconds are returned as float, nanoseconds as int.

        :param nanoseconds: True to measure time in nanoseconds, False to measure time in seconds (default).
        """
        self._start_time = None
        self._nanoseconds: bool = nanoseconds

        self.running: bool = False
        self.last_measure = None

    def start(self):
        """Start a new timer"""

        if self._start_time is not None:
            raise TimerError(f"Timer is running. Use .stop() to stop it")

        if self._nanoseconds:
            self._start_time = time.perf_counter_ns()
        else:
            self._start_time = time.perf_counter()

        self.running = True

    def restart(self):
        """Reset the timer"""

        self._start_time = None
        self.start()

    def measure(self):
        """Measure the elapsed time"""

        # if self._start_time is None and self.last_measure is None:
        #     raise TimerError(f"Timer is not running. Use .start() to start it")

        # If the timer is running, measure the elapsed time. If not, return the last measured time.
        if self.running:
            if self._nanoseconds:
                self.last_measure = time.perf_counter_ns() - self._start_time
            else:
                self.last_measure = time.perf_counter() - self._start_time

        return self.last_measure

    def stop(self, measure: bool = True):
        """
        Stop the timer, and report the elapsed time

        :param measure: True to measure the elapsed time, False to stop the timer without measuring.
            Measuring, means that the timer will return the elapsed time and 'self.last_measure' will be updated.
        """

        elapsed_time = None
        if measure:
            elapsed_time = self.measure()

        self._start_time = None
        self.running = False

        return elapsed_time

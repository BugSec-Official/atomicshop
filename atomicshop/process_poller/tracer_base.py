import threading

from .. import get_process_list


class Tracer:
    """
    Main tracer class for getting the list of processes.
    """

    def __init__(self):
        self.tracer_instance = None
        self.process_queue = None

        self._cycle_callable = None
        self._processes = {}

    def start(self):
        """
        Start the tracer.
        """

        self._processes = get_process_list.GetProcessList(
            get_method='pywin32', connect_on_init=True).get_processes(as_dict=True)

        self.process_queue.put(self._processes)

        self.tracer_instance.start()

        thread = threading.Thread(target=self.update_queue)
        thread.daemon = True
        thread.start()

    def update_queue(self):
        """
        Update the list of processes.
        """

        while True:
            # Get subclass specific get process cycle.
            current_processes = self._cycle_callable()

            self._processes.update(current_processes)

            self.process_queue.put(self._processes)

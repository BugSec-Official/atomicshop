import threading
import multiprocessing
import time

from .wrappers.pywin32w import wmi_win32process
from .wrappers import psutilw
from .basics import list_of_dicts, dicts


class ProcessPollerPool:
    """
    The class is responsible for polling processes and storing them in a pool.
    Currently, this works with 'psutil' library and takes up to 16% of CPU on my machine.
    Because 'psutil' fetches 'cmdline' for each 'pid' dynamically, and it takes time and resources
    Later, I'll find a solution to make it more efficient.
    """
    def __init__(
            self, store_cycles: int = 1, interval_seconds: float = 0, operation: str = 'thread',
            poller_method: str = 'pywin32'):
        """
        :param store_cycles: int, how many cycles to store. Each cycle is polling processes.
            Example: Specifying 3 will store last 3 polled cycles of processes.
            Default is 1, which means that only the last cycle will be stored.
        :param interval_seconds: float, how many seconds to wait between each cycle.
            Default is 0, which means that the polling will be as fast as possible.
        :param operation: str, 'thread' or 'process'. Default is 'process'.
            'thread': The polling will be done in a new thread.
            'process': The polling will be done in a new process.
        :param poller_method: str. Default is 'pywin32'. Available:
            'psutil': Process Polling done by 'psutil', very slow and inefficient, if you're doing more stuff with
                'psutil' - it will be slow.
            'pywin32': Process Polling done by 'pywin32', querying WMI, which is twice faster than psutil.
        """

        self.store_cycles: int = store_cycles
        self.interval_seconds: float = interval_seconds
        self.operation: str = operation
        self.poller_method: str = poller_method

        if self.poller_method == 'psutil':
            self.process_polling_instance = psutilw.PsutilProcesses()
        elif self.poller_method == 'pywin32':
            self.process_polling_instance = wmi_win32process.Pywin32Processes()

        # Current process pool.
        self.processes: dict = dict()

        # The variable is responsible to stop the thread if it is running.
        self.running: bool = False

        self.queue = multiprocessing.Queue()

    def start(self):
        # if self.poller_method == 'pywin32':
        #     self.process_polling_instance.connect()

        if self.operation == 'thread':
            self._start_thread()
        elif self.operation == 'process':
            self._start_process()
        else:
            raise ValueError(f'Invalid operation type [{self.operation}]')

    def stop(self):
        self.running = False

    def _start_thread(self):
        self.running = True
        # threading.Thread(target=self._worker, args=(self.process_polling_instance,)).start()
        threading.Thread(target=self._worker).start()

    def _start_process(self):
        self.running = True
        multiprocessing.Process(target=self._worker).start()
        threading.Thread(target=self._thread_get_queue).start()

    # def _worker(self, process_polling_instance):
    def _worker(self):
        if self.poller_method == 'pywin32':
            # We must initiate the connection inside the thread/process, because it is not thread-safe.
            self.process_polling_instance.connect()

        list_of_processes: list = list()
        while self.running:
            # If the list is full (to specified 'store_cycles'), remove the first element.
            if len(list_of_processes) == self.store_cycles:
                del list_of_processes[0]

            current_processes: dict = dict()
            # If poller_method is 'psutil'.
            if self.poller_method == 'psutil':
                # Get processes as dict.
                current_processes = self.process_polling_instance.get_processes_as_dict(
                    attrs=['pid', 'name', 'cmdline'], cmdline_to_string=True)
            # If poller_method is 'pywin32'.
            elif self.poller_method == 'pywin32':
                # Get processes as dict.
                current_processes = self.process_polling_instance.get_processes_as_dict(
                    attrs=['ProcessId', 'Name', 'CommandLine'])

                # Convert the keys from WMI to the keys that are used in 'psutil'.
                converted_process_dict = dict()
                for pid, process_info in current_processes.items():
                    converted_process_dict[pid] = dicts.convert_key_names(
                        process_info, {'Name': 'name', 'CommandLine': 'cmdline'})

                current_processes = converted_process_dict

            # Append the current processes to the list.
            list_of_processes.append(current_processes)

            # Merge all dicts in the list to one dict, updating with most recent PIDs.
            self.processes = list_of_dicts.merge_to_dict(list_of_processes)

            if self.operation == 'process':
                self.queue.put(self.processes)

            time.sleep(self.interval_seconds)

    def _thread_get_queue(self):
        while True:
            self.processes = self.queue.get()

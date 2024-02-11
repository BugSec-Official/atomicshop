import threading
import multiprocessing
import time
from typing import Literal, Union

from .wrappers.pywin32w import wmi_win32process
from .wrappers.psutilw import psutilw
from .basics import list_of_dicts, dicts
from .process_name_cmd import ProcessNameCmdline


def get_process_time_tester(
        get_method: Literal['psutil', 'pywin32', 'process_dll'] = 'process_dll',
        times_to_test: int = 50
):
    """
    The function will test the time it takes to get the list of processes with different methods and cycles.

    :param get_method: str, The method to get the list of processes. Default is 'process_list_dll'.
        'psutil': Get the list of processes by 'psutil' library. Resource intensive and slow.
        'pywin32': Get the list of processes by 'pywin32' library, using WMI. Not resource intensive, but slow.
        'process_dll'. Not resource intensive and fast. Probably works only in Windows 10 x64
    :param times_to_test: int, how many times to test the function.
    """

    import timeit

    setup_code = '''
from atomicshop import process_poller
get_process_list = process_poller.GetProcessList(get_method=get_method, connect_on_init=True)
'''

    test_code = '''
test = get_process_list.get_processes()
'''

    # globals need to be specified, otherwise the setup_code won't work with passed variables.
    times = timeit.timeit(setup=setup_code, stmt=test_code, number=times_to_test, globals=locals())
    print(f'Execution time: {times}')


class GetProcessList:
    def __init__(
            self,
            get_method: Literal['psutil', 'pywin32', 'process_dll'] = 'process_dll',
            connect_on_init: bool = False
    ):
        """
        :param get_method: str, The method to get the list of processes. Default is 'process_list_dll'.
            'psutil': Get the list of processes by 'psutil' library. Resource intensive and slow.
            'pywin32': Get the list of processes by 'pywin32' library, using WMI. Not resource intensive, but slow.
            'process_dll'. Not resource intensive and fast. Probably works only in Windows 10 x64
        :param connect_on_init: bool, if True, will connect to the service on init. 'psutil' don't need to connect.
        """
        self.get_method = get_method
        self.process_polling_instance = None

        self.connected = False

        if self.get_method == 'psutil':
            self.process_polling_instance = psutilw.PsutilProcesses()
            self.connected = True
        elif self.get_method == 'pywin32':
            self.process_polling_instance = wmi_win32process.Pywin32Processes()
        elif self.get_method == 'process_dll':
            self.process_polling_instance = ProcessNameCmdline()

        if connect_on_init:
            self.connect()

    def connect(self):
        """
        Connect to the service. 'psutil' don't need to connect.
        """

        # If the service is not connected yet. Since 'psutil' don't need to connect.
        if not self.connected:
            if self.get_method == 'pywin32':
                self.process_polling_instance.connect()
                self.connected = True
            elif self.get_method == 'process_dll':
                self.process_polling_instance.load()
                self.connected = True

    def get_processes(self, as_dict: bool = True) -> Union[list, dict]:
        """
        The function will get the list of opened processes and return it as a list of dicts.

        :return: list of dicts, of opened processes.
        """

        if as_dict:
            if self.get_method == 'psutil':
                return self.process_polling_instance.get_processes_as_dict(
                    attrs=['pid', 'name', 'cmdline'], cmdline_to_string=True)
            elif self.get_method == 'pywin32':
                processes = self.process_polling_instance.get_processes_as_dict(
                    attrs=['ProcessId', 'Name', 'CommandLine'])

                # Convert the keys from WMI to the keys that are used in 'psutil'.
                converted_process_dict = dict()
                for pid, process_info in processes.items():
                    converted_process_dict[pid] = dicts.convert_key_names(
                        process_info, {'Name': 'name', 'CommandLine': 'cmdline'})

                return converted_process_dict
            elif self.get_method == 'process_dll':
                return self.process_polling_instance.get_process_details(as_dict=True)
        else:
            if self.get_method == 'psutil':
                return self.process_polling_instance.get_processes_as_list_of_dicts(
                    attrs=['pid', 'name', 'cmdline'], cmdline_to_string=True)
            elif self.get_method == 'pywin32':
                processes = self.process_polling_instance.get_processes_as_list_of_dicts(
                    attrs=['ProcessId', 'Name', 'CommandLine'])

                # Convert the keys from WMI to the keys that are used in 'psutil'.
                for process_index, process_info in enumerate(processes):
                    processes[process_index] = dicts.convert_key_names(
                        process_info, {'ProcessId': 'pid', 'Name': 'name', 'CommandLine': 'cmdline'})

                return processes
            elif self.get_method == 'process_dll':
                return self.process_polling_instance.get_process_details(as_dict=as_dict)


class ProcessPollerPool:
    """
    The class is responsible for polling processes and storing them in a pool.
    Currently, this works with 'psutil' library and takes up to 16% of CPU on my machine.
    Because 'psutil' fetches 'cmdline' for each 'pid' dynamically, and it takes time and resources
    Later, I'll find a solution to make it more efficient.
    """
    def __init__(
            self, store_cycles: int = 200,
            interval_seconds: Union[int, float] = 0,
            operation: Literal['thread', 'process'] = 'thread',
            poller_method: Literal['psutil', 'pywin32', 'process_dll'] = 'process_dll'
    ):
        """
        :param store_cycles: int, how many cycles to store. Each cycle is polling processes.
            Example: Specifying 3 will store last 3 polled cycles of processes.

            Default is 200, which means that 200 latest cycles original PIDs and their process names will be stored.

            You can execute the 'get_process_time_tester' function in order to find the optimal number of cycles
            and how much time it will take.
        :param interval_seconds: float, how many seconds to wait between each cycle.
            Default is 0, which means that the polling will be as fast as possible.

            Basically, you want it to be '0' if you want to get the most recent processes.
            Any polling by itself takes time, so if you want to get the most recent processes, you want to do it as fast
            as possible.
        :param operation: str, 'thread' or 'process'. Default is 'process'.
            'process': The polling will be done in a new process.
            'thread': The polling will be done in a new thread.

            Python is slow, if you are going to use 'thread' all other operations inside this thread will be very slow.
            You can even get exceptions, if you're using process polling for correlations of PIDs and process names.
            It is advised to use the 'process' operation, which will not affect other operations in the thread.
        :param poller_method: str. Default is 'process_dll'. Available:
            'psutil': Get the list of processes by 'psutil' library. Resource intensive and slow.
            'pywin32': Get the list of processes by 'pywin32' library, using WMI. Not resource intensive, but slow.
            'process_dll'. Not resource intensive and fast. Probably works only in Windows 10 x64.
        """

        self.store_cycles: int = store_cycles
        self.interval_seconds: float = interval_seconds
        self.operation: str = operation
        self.poller_method = poller_method

        self.get_processes_list = GetProcessList(get_method=self.poller_method)

        # Current process pool.
        self.processes: dict = dict()

        # The variable is responsible to stop the thread if it is running.
        self.running: bool = False

        self.queue = multiprocessing.Queue()

    def start(self):
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
        # We must initiate the connection inside the thread/process, because it is not thread-safe.
        self.get_processes_list.connect()

        list_of_processes: list = list()
        while self.running:
            # If the list is full (to specified 'store_cycles'), remove the first element.
            if len(list_of_processes) == self.store_cycles:
                del list_of_processes[0]

            # Get the current processes and reinitialize the instance of the dict.
            current_processes: dict = dict(self.get_processes_list.get_processes())

            # Remove Command lines that contains only numbers, since they are useless.
            for pid, process_info in current_processes.items():
                if process_info['cmdline'].isnumeric():
                    current_processes[pid]['cmdline'] = str()
                elif process_info['cmdline'] == 'Error':
                    current_processes[pid]['cmdline'] = str()

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

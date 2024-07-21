import threading
import multiprocessing
import time
from typing import Literal, Union
from pathlib import Path

from .wrappers.pywin32w import wmi_win32process
from .wrappers.pywin32w.win_event_log.subscribes import subscribe_to_process_create
from .wrappers.psutilw import psutilw
from .etws.traces import trace_sysmon_process_creation
from .basics import dicts
from .process_name_cmd import ProcessNameCmdline
from .print_api import print_api


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
    """
    The class is responsible for getting the list of running processes.

    Example of one time polling with 'pywin32' method:
    from atomicshop import process_poller
    process_list: dict = \
        process_poller.GetProcessList(get_method='pywin32', connect_on_init=True).get_processes(as_dict=True)
    """
    def __init__(
            self,
            get_method: Literal['psutil', 'pywin32', 'process_dll'] = 'process_dll',
            connect_on_init: bool = False
    ):
        """
        :param get_method: str, The method to get the list of processes. Default is 'process_list_dll'.
            'psutil': Get the list of processes by 'psutil' library. Resource intensive and slow.
            'pywin32': Get the list of processes by 'pywin32' library, using WMI. Not resource intensive, but slow.
            'process_dll'. Not resource intensive and fast. Probably works only in Windows 10 x64.
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

        :return: dict while key is pid or list of dicts, of opened processes (depending on 'as_dict' setting).
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
            self,
            interval_seconds: Union[int, float] = 0,
            operation: Literal['thread', 'process'] = 'thread',
            poller_method: Literal['psutil', 'pywin32', 'process_dll', 'sysmon_etw', 'event_log'] = 'event_log',
            sysmon_etw_session_name: str = None,
            sysmon_directory: str = None
    ):
        """
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
            'sysmon_etw': Get the list of processes with running SysMon by ETW - Event Tracing for Windows.
                In this case 'store_cycles' and 'interval_seconds' are irrelevant, since the ETW is real-time.
                Steps we take:
                    1. Check if SysMon is Running. If not, check if the executable exists in specified
                        location and start it as a service.
                    2. Start the "Microsoft-Windows-Sysmon" ETW session.
                    3. Take a snapshot of current processes and their CMDs with psutil and store it in a dict.
                    4. Each new process creation from ETW updates the dict.
            'event_log': Get the list of processes by subscribing to the Windows Event Log.
                Log Channel: Security, Event ID: 4688.
                We enable the necessary prerequisites in registry and subscribe to the event.
        :param sysmon_etw_session_name: str, only for 'sysmon_etw' get_method.
            The name of the ETW session for tracing process creation.
        :param sysmon_directory: str, only for 'sysmon_etw' get_method.
            The directory where the SysMon executable is located. If non-existed will be downloaded.
        ---------------------------------------------
        If there is an exception, ProcessPollerPool.processes will be set to the exception.
        While getting the processes you can use this to execute the exception:

        processes = ProcessPollerPool.processes

        if isinstance(processes, BaseException):
            raise processes
        """

        self.interval_seconds: float = interval_seconds
        self.operation: str = operation
        self.poller_method = poller_method
        self.sysmon_etw_session_name: str = sysmon_etw_session_name
        self.sysmon_directory: str = sysmon_directory

        # Current process pool.
        self._processes: dict = dict()

        # The variable is responsible to stop the thread if it is running.
        self._running: bool = False

        self._process_queue = multiprocessing.Queue()
        self._running_state_queue = multiprocessing.Queue()

    def start(self):
        if self.operation == 'thread':
            self._start_thread()
        elif self.operation == 'process':
            self._start_process()
        else:
            raise ValueError(f'Invalid operation type [{self.operation}]')

        thread = threading.Thread(target=self._thread_get_queue)
        thread.daemon = True
        thread.start()

    def stop(self):
        self._running = False
        self._running_state_queue.put(False)

    def get_processes(self):
        return self._processes

    def _start_thread(self):
        self._running = True

        thread = threading.Thread(
            target=_worker, args=(
                self.poller_method, self._running_state_queue, self.interval_seconds,
                self._process_queue, self.sysmon_etw_session_name, self.sysmon_directory,
            )
        )
        thread.daemon = True
        thread.start()

    def _start_process(self):
        self._running = True
        multiprocessing.Process(
            target=_worker, args=(
                self.poller_method, self._running_state_queue, self.interval_seconds,
                self._process_queue, self.sysmon_etw_session_name, self.sysmon_directory,
            )).start()

    def _thread_get_queue(self):
        while True:
            self._processes = self._process_queue.get()


def _worker(
        poller_method, running_state_queue, interval_seconds, process_queue, sysmon_etw_session_name, sysmon_directory):
    def _worker_to_get_running_state():
        nonlocal running_state
        running_state = running_state_queue.get()

    running_state: bool = True

    thread = threading.Thread(target=_worker_to_get_running_state)
    thread.daemon = True
    thread.start()

    if poller_method == 'sysmon_etw':
        poller_instance = trace_sysmon_process_creation.SysmonProcessCreationTrace(
            attrs=['pid', 'original_file_name', 'command_line'],
            session_name=sysmon_etw_session_name,
            close_existing_session_name=True,
            sysmon_directory=sysmon_directory
        )

        # We must initiate the connection inside the thread/process, because it is not thread-safe.
        poller_instance.start()

        processes = GetProcessList(get_method='pywin32', connect_on_init=True).get_processes(as_dict=True)
        process_queue.put(processes)
    elif poller_method == 'event_log':
        poller_instance = subscribe_to_process_create.ProcessCreateSubscriber()
        poller_instance.start()

        processes = GetProcessList(get_method='pywin32', connect_on_init=True).get_processes(as_dict=True)
        process_queue.put(processes)
    else:
        poller_instance = GetProcessList(get_method=poller_method)
        poller_instance.connect()
        processes = {}

    exception = None
    list_of_processes: list = list()
    while running_state:
        try:
            if poller_method == 'sysmon_etw':
                # Get the current processes and reinitialize the instance of the dict.
                current_cycle: dict = poller_instance.emit()
                current_processes: dict = {int(current_cycle['pid']): {
                    'name': current_cycle['original_file_name'],
                    'cmdline': current_cycle['command_line']}
                }
            elif poller_method == 'event_log':
                # Get the current processes and reinitialize the instance of the dict.
                current_cycle: dict = poller_instance.emit()
                current_processes: dict = {current_cycle['pid']: {
                    'name': Path(current_cycle['process_name']).name,
                    'cmdline': current_cycle['command_line']}
                }
            else:
                # Get the current processes and reinitialize the instance of the dict.
                current_processes: dict = dict(poller_instance.get_processes())

            # Remove Command lines that contains only numbers, since they are useless.
            for pid, process_info in current_processes.items():
                if process_info['cmdline'].isnumeric():
                    current_processes[pid]['cmdline'] = str()
                elif process_info['cmdline'] == 'Error':
                    current_processes[pid]['cmdline'] = str()

            # This loop is essential for keeping the command lines.
            # When the process unloads from memory, the last polling will have only pid and executable name, but not
            # the command line. This loop will keep the command line from the previous polling if this happens.
            for pid, process_info in current_processes.items():
                if pid in processes:
                    if processes[pid]['name'] == current_processes[pid]['name']:
                        if current_processes[pid]['cmdline'] == '':
                            current_processes[pid]['cmdline'] = processes[pid]['cmdline']
            processes.update(current_processes)

            process_queue.put(processes)

            # Since ETW is a blocking operation, we don't need to sleep.
            if poller_method != 'sysmon_etw':
                time.sleep(interval_seconds)
        except KeyboardInterrupt as e:
            running_state = False
            exception = e
        except Exception as e:
            running_state = False
            exception = e
            print_api(f'Exception in ProcessPollerPool: {e}', color='red')
            raise

    if not running_state:
        process_queue.put(exception)

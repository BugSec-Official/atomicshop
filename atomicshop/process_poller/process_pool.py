import threading
import multiprocessing
import time
from typing import Literal, Union

from .tracers import sysmon_etw, event_log
from .pollers import psutil_pywin32wmi_dll
from ..wrappers.pywin32w.win_event_log.subscribes import process_terminate


POLLER_SETTINGS_SYSMON_ETW: dict = {
    'etw_session_name': None,           # Default will be used, check 'trace_sysmon_process_creation' for details.
    'sysmon_directory': None            # Directory, where sysmon.exe is located. Default will be used.
}


class ProcessPool:
    """
    The class is responsible for getting processes and storing them in a pool.
    THE POOL OF PROCESSES IS NOT REAL TIME!!!
    There can be several moments delay (less than a second) + you can add delay before pid removal from the pool.
    This is needed only to correlate PIDs to process names and command lines of other events you get on Windows.
    """
    def __init__(
            self,
            operation: Literal['thread', 'process'] = 'thread',
            interval_seconds: Union[int, float] = 0,
            process_get_method: Literal[
                'poll_psutil',
                'poll_pywin32',
                'poll_process_dll',
                'trace_sysmon_etw',
                'trace_event_log'
            ] = 'trace_event_log',
            poller_settings: dict = None,
            process_terminator: bool = True,
            wait_before_pid_remove_seconds: float = 5
    ):
        """
        :param operation: str, 'thread' or 'process'. Default is 'process'.
            'process': The polling will be done in a new process.
            'thread': The polling will be done in a new thread.

            Python is slow, if you are going to use 'thread' all other operations inside this thread will be very slow.
            You can even get exceptions, if you're using process polling for correlations of PIDs and process names.
            It is advised to use the 'process' operation, which will not affect other operations in the thread.
        :param interval_seconds: works only for pollers, float, how many seconds to wait between each cycle.
            Default is 0, which means that the polling will be as fast as possible.

            Basically, you want it to be '0' if you want to get the most recent processes.
            Any polling by itself takes time, so if you want to get the most recent processes, you want to do it as fast
            as possible.
        :param process_get_method: str. Default is 'process_dll'. Available:
            'poll_psutil': Poller, Get the list of processes by 'psutil' library. Resource intensive and slow.
            'poll_pywin32': Poller, processes by 'pywin32' library, using WMI. Not resource intensive, but slow.
            'poll_process_dll'. Poller, Not resource intensive and fast. Probably works only in Windows 10 x64.
            'trace_sysmon_etw': Tracer, Get the list of processes with running SysMon by ETW - Event Tracing.
                In this case 'interval_seconds' is irrelevant, since the ETW is real-time.
                Steps we take:
                    1. Check if SysMon is Running. If not, check if the executable exists in specified
                        location and start it as a service.
                    2. Start the "Microsoft-Windows-Sysmon" ETW session.
                    3. Take a snapshot of current processes and their CMDs with psutil and store it in a dict.
                    4. Each new process creation from ETW updates the dict.
            'trace_event_log': Get the list of processes by subscribing to the Windows Event Log.
                Log Channel: Security, Event ID: 4688.
                We enable the necessary prerequisites in registry and subscribe to the event.
        :param poller_settings: dict, settings for the poller method.
            'sysmon_etw': If not set 'POLLER_SETTINGS_SYSMON_ETW' will be used.
        :param process_terminator: bool, if True, process terminator will run in the background and monitor
            the processes for termination. If the process is terminated it will be removed from the pool.
        :param wait_before_pid_remove_seconds: float, how many seconds to wait before the process is removed from
            the pool after process termination event is received for that pid.
        ---------------------------------------------
        If there is an exception, ProcessPollerPool.processes will be set to the exception.
        While getting the processes you can use this to execute the exception:

        processes = ProcessPollerPool.processes

        if isinstance(processes, BaseException):
            raise processes
        """

        self.operation: str = operation
        self.interval_seconds: float = interval_seconds
        self.process_get_method = process_get_method
        self.process_terminator: bool = process_terminator
        self.wait_before_pid_remove_seconds: float = wait_before_pid_remove_seconds
        self.poller_settings: dict = poller_settings

        if self.poller_settings is None:
            if process_get_method == 'sysmon_etw':
                self.poller_settings: dict = POLLER_SETTINGS_SYSMON_ETW

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

        thread_get_queue = threading.Thread(target=self._thread_get_queue)
        thread_get_queue.daemon = True
        thread_get_queue.start()

        if self.process_terminator:
            thread_process_termination = threading.Thread(target=self._thread_process_termination)
            thread_process_termination.daemon = True
            thread_process_termination.start()

    def stop(self):
        self._running = False
        self._running_state_queue.put(False)

    def get_processes(self):
        return self._processes

    def _get_args_for_worker(self):
        return self.process_get_method, self.interval_seconds, self._process_queue, self.poller_settings

    def _start_thread(self):
        self._running = True

        thread = threading.Thread(target=_worker, args=(self._get_args_for_worker()))
        thread.daemon = True
        thread.start()

    def _start_process(self):
        self._running = True
        multiprocessing.Process(target=_worker, args=(self._get_args_for_worker())).start()

    def _thread_get_queue(self):
        while True:
            self._processes = self._process_queue.get()

    def _thread_process_termination(self):
        process_terminate_instance = process_terminate.ProcessTerminateSubscriber()
        process_terminate_instance.start()

        while True:
            termination_event = process_terminate_instance.emit()
            process_id = termination_event['ProcessIdInt']

            removal_thread = threading.Thread(target=self._remove_pid, args=(process_id,))
            removal_thread.daemon = True
            removal_thread.start()

    def _remove_pid(self, process_id):
        # We need to wait a bit before we remove the process.
        # This is because termination event can come sooner than the creation and the process
        # is not yet in the pool.
        # This happens mostly when the process is terminated immediately after the creation.
        # Example: ping example.c
        # 'example.c' is not a valid address, so the process is terminated immediately after the creation.
        counter = 0
        while counter < 30:
            if process_id in self._processes:
                break
            counter += 1
            time.sleep(0.1)

        if counter == 30:
            # print_api(f'Process [{process_id}] not found in the pool.', color='yellow')
            return

        # time.sleep(1)
        # if process_id not in self._processes:
        #     print_api(f'Process [{process_id}] not found in the pool.', color='red')
        #     return

        time.sleep(self.wait_before_pid_remove_seconds)
        _ = self._processes.pop(process_id, None)
        # print_api(f'Process [{process_id}] removed from the pool.', color='yellow')


def _worker(
        poller_method,
        interval_seconds,
        process_queue,
        poller_settings
):

    if poller_method == 'trace_sysmon_etw':
        get_instance = sysmon_etw.TracerSysmonEtw(settings=poller_settings, process_queue=process_queue)
    elif poller_method == 'trace_event_log':
        get_instance = event_log.TracerEventlog(process_queue=process_queue)
    elif 'poll_' in poller_method:
        get_instance = psutil_pywin32wmi_dll.PollerPsutilPywin32Dll(
            interval_seconds=interval_seconds, process_get_method=poller_method, process_queue=process_queue)
    else:
        raise ValueError(f'Invalid poller method [{poller_method}]')

    # We must initiate the connection inside the thread/process, because it is not thread-safe.
    get_instance.start()

    while True:
        time.sleep(1)

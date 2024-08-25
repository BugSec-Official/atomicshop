import threading
from pathlib import Path
import time

from ..wrappers.pywin32w.win_event_log.subscribes import process_create, process_terminate
from .. import get_process_list


WAIT_BEFORE_PROCESS_TERMINATION_CHECK_SECONDS: float = 3
WAIT_BEFORE_PROCESS_TERMINATION_CHECK_COUNTS: float = WAIT_BEFORE_PROCESS_TERMINATION_CHECK_SECONDS * 10


class SimpleProcessPool:
    """
    THE POOL OF PROCESSES IS NOT REAL TIME!!!
    There can be several moments delay (less than a second) + you can add delay before pid removal from the pool.
    This is needed only to correlate PIDs to process names and command lines of other events you get on Windows.
    The idea is similar to the process_poller.process_pool.ProcessPool class, but this class is simpler and uses
    only the pywin32 tracing of the Windows Event Log Process Creation and Process Termination events.
    The simple process pool is used to get things simpler than the process_pool.ProcessPool class.
    """

    def __init__(
            self,
            wait_before_pid_remove_seconds: float = 5
    ):
        """
        :param wait_before_pid_remove_seconds: float, how many seconds to wait before the process is removed from
            the pool after process termination event is received for that pid.
        """

        self.wait_before_pid_remove_seconds: float = wait_before_pid_remove_seconds

        self._processes: dict = dict()
        self._running: bool = False

    def start(self):
        self._running = True

        self._processes = get_process_list.GetProcessList(
            get_method='pywin32', connect_on_init=True).get_processes(as_dict=True)

        thread_get_queue = threading.Thread(target=self._start_main_thread)
        thread_get_queue.daemon = True
        thread_get_queue.start()

        thread_process_termination = threading.Thread(target=self._thread_process_termination)
        thread_process_termination.daemon = True
        thread_process_termination.start()

    def stop(self):
        self._running = False

    def get_processes(self):
        return self._processes

    def _start_main_thread(self):
        get_instance = process_create.ProcessCreateSubscriber()
        get_instance.start()

        while self._running:
            event = get_instance.emit()
            process_id = event['NewProcessIdInt']
            process_name = Path(event['NewProcessName']).name
            command_line = event['CommandLine']

            self._processes[process_id] = {
                'name': process_name,
                'cmdline': command_line
            }

            # print_api(f'Process [{process_id}] added to the pool.', color='blue')

    def _thread_process_termination(self):
        process_terminate_instance = process_terminate.ProcessTerminateSubscriber()
        process_terminate_instance.start()

        while self._running:
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
        while counter < WAIT_BEFORE_PROCESS_TERMINATION_CHECK_COUNTS:
            if process_id in self._processes:
                break
            counter += 1
            time.sleep(0.1)

        if counter == WAIT_BEFORE_PROCESS_TERMINATION_CHECK_COUNTS:
            # print_api(f'Process [{process_id}] not found in the pool.', color='yellow')
            return

        # time.sleep(1)
        # if process_id not in self._processes:
        #     print_api(f'Process [{process_id}] not found in the pool.', color='red')
        #     return

        time.sleep(self.wait_before_pid_remove_seconds)
        _ = self._processes.pop(process_id, None)
        # print_api(f'Process [{process_id}] removed from the pool.', color='yellow')

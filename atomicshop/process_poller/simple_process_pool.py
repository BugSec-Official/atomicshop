import threading
from pathlib import Path
import time
import multiprocessing.managers

from ..wrappers.pywin32w.win_event_log.subscribes import process_create, process_terminate
from .. import get_process_list, get_process_name_cmd_dll
from ..print_api import print_api


WAIT_BEFORE_PROCESS_TERMINATION_CHECK_SECONDS: float = 3
WAIT_BEFORE_PROCESS_TERMINATION_CHECK_COUNTS: float = WAIT_BEFORE_PROCESS_TERMINATION_CHECK_SECONDS * 10

WAIT_FOR_PROCESS_POLLER_PID_SECONDS: int = 3
WAIT_FOR_PROCESS_POLLER_PID_COUNTS: int = WAIT_FOR_PROCESS_POLLER_PID_SECONDS * 10


class SimpleProcessPool:
    """
    THE POOL OF PROCESSES IS NOT REAL TIME!!!
    There can be several moments delay (less than a second) + you can add delay before pid removal from the pool.
    This is needed only to correlate PIDs to process names and command lines of other events you get on Windows.
    The idea is similar to the process_poller.process_pool.ProcessPool class, but this class is simpler and uses
    only the pywin32 tracing of the Windows Event Log Process Creation and Process Termination events.
    The simple process pool is used to get things simpler than the process_pool.ProcessPool class.

    Example of starting the process pool in multiprocess:
        import sys

        from atomicshop.process_poller import simple_process_pool


        def start_process_pool(process_pool_shared_dict_proxy):
            process_poller = simple_process_pool.SimpleProcessPool(
                process_pool_shared_dict_proxy=process_pool_shared_dict_proxy)
            process_poller.start()

            try:
                # Keep the process alive.
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                process_poller.stop()


        def main():
            # Create the shared multiprocessing dictionary of the process pool.
            manager = multiprocessing.Manager()
            multiprocess_dict_proxy = manager.dict()

            # Start the process pool in a separate process.
            pool_process = multiprocessing.Process(target=start_process_pool, args=(multiprocess_dict_proxy,))
            pool_process.start()

            # Pass the shared dict proxy to other functions.


        if __name__ == '__main__':
            sys.exit(main())
    """

    def __init__(
            self,
            wait_before_pid_remove_seconds: float = 5,
            process_pool_shared_dict_proxy: multiprocessing.managers.DictProxy = None
    ):
        """
        :param wait_before_pid_remove_seconds: float, how many seconds to wait before the process is removed from
            the pool after process termination event is received for that pid.
        :param process_pool_shared_dict_proxy: multiprocessing.managers.DictProxy, shared dict proxy to update
            the process pool.
            If you run a function from other multiprocessing.Process, you can pass the shared_dict_proxy to the function
            and update the process pool from that function.

            Example:
            import multiprocessing.managers

            manager: multiprocessing.managers.SyncManager = multiprocessing.Manager()
            multiprocess_dict_proxy: multiprocessing.managers.DictProxy = manager.dict()

            process_poller = SimpleProcessPool()
            process_poller.start()

            while True:
                #============================
                # your function where you get info with pid
                # result = {
                #    'pid': 1234,
                #    'info': 'some info'
                # }
                #============================
                info_with_process_details = {
                    'pid': result['pid'],
                    'info': result['info']
                    'process_details': shared_dict_proxy[result['pid']]
                }

                break

            process_poller.stop()
            manager.shutdown()
        """

        self.wait_before_pid_remove_seconds: float = wait_before_pid_remove_seconds
        self.process_pool_shared_dict_proxy: multiprocessing.managers.DictProxy = process_pool_shared_dict_proxy

        self._processes: dict = dict()
        self._running: bool = False

    def start(self):
        self._running = True

        self._processes = get_process_list.GetProcessList(
            get_method='pywin32', connect_on_init=True).get_processes(as_dict=True)

        thread_get_queue = threading.Thread(target=self._start_main_thread, args=(self.process_pool_shared_dict_proxy,))
        thread_get_queue.daemon = True
        thread_get_queue.start()

        thread_process_termination = threading.Thread(target=self._thread_process_termination)
        thread_process_termination.daemon = True
        thread_process_termination.start()

    def stop(self):
        self._running = False

    def get_processes(self):
        return self._processes

    def _start_main_thread(self, process_pool_shared_dict_proxy):
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

            # Update the multiprocessing shared dict proxy.
            if process_pool_shared_dict_proxy is not None:
                process_pool_shared_dict_proxy.clear()
                process_pool_shared_dict_proxy.update(self._processes)

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


class PidProcessConverter:
    """
    This class is used to get the process details by PID from the process pool shared dict proxy.
    """

    def __init__(
            self,
            process_pool_shared_dict_proxy: multiprocessing.managers.DictProxy
    ):
        """
        :param process_pool_shared_dict_proxy: multiprocessing.managers.DictProxy, multiprocessing shared dict proxy.
        """

        self.process_pool_shared_dict_proxy: multiprocessing.managers.DictProxy = process_pool_shared_dict_proxy

        self.get_process_with_dll_instance = get_process_name_cmd_dll.ProcessNameCmdline(load_dll=True)

    def get_process_by_pid(self, pid: int):
        """
        THIS FUNCTION WILL RUN OUTSIDE THE PROCESS POOL PROCESS. Inside the function that needs
        the pid to process conversion.
        Get the process details by PID from the process pool shared dict proxy.

        :param pid: int, the process ID.
        :return: dict, the process details.
        """

        counter = 0
        process_dict: dict = dict()
        while counter < WAIT_FOR_PROCESS_POLLER_PID_COUNTS:
            if pid not in self.process_pool_shared_dict_proxy:
                # print(dict(self.process_pool_shared_dict_proxy))
                time.sleep(0.1)
                counter += 1
            else:
                process_dict = self.process_pool_shared_dict_proxy[pid]
                break

        if counter == WAIT_FOR_PROCESS_POLLER_PID_COUNTS and not process_dict:
            print_api(f"Error: The PID [{pid}] is not in the pool, trying DLL snapshot.", color='yellow')
            # Last resort, try to get the process name by current process snapshot.
            processes = self.get_process_with_dll_instance.get_process_details(as_dict=True)
            if pid not in processes:
                print_api(f"Error: Couldn't get the process name for PID: {pid}.", color='red')
                process_dict = {
                    'name': pid,
                    'cmdline': ''
                }
            else:
                process_dict = processes[pid]

        return process_dict


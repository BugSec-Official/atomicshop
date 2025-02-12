import threading
from pathlib import Path
import time
import multiprocessing.managers
import queue


from ..wrappers.pywin32w.win_event_log.subscribes import process_create, process_terminate
from .. import get_process_list
from ..print_api import print_api


WAIT_BEFORE_PROCESS_TERMINATION_CHECK_SECONDS: float = 3
WAIT_BEFORE_PROCESS_TERMINATION_CHECK_COUNTS: float = WAIT_BEFORE_PROCESS_TERMINATION_CHECK_SECONDS * 10

WAIT_FOR_PROCESS_POLLER_PID_SECONDS: int = 3
WAIT_FOR_PROCESS_POLLER_PID_COUNTS: int = WAIT_FOR_PROCESS_POLLER_PID_SECONDS * 10


class PidProcessConverterPIDNotFoundError(Exception):
    pass


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
        self.shared_dict_update_queue: queue.Queue = queue.Queue()
        self.empty_cmdline_queue: queue.Queue = queue.Queue()

    def start(self):
        self._running = True

        self._processes = get_process_list.GetProcessList(
            get_method='psutil', connect_on_init=True).get_processes(as_dict=True)

        thread_get_queue = threading.Thread(target=self._start_main_thread, args=(self.shared_dict_update_queue,))
        thread_get_queue.daemon = True
        thread_get_queue.start()

        thread_process_termination = threading.Thread(target=self._thread_process_termination)
        thread_process_termination.daemon = True
        thread_process_termination.start()

        thread_get_psutil_commandline = threading.Thread(target=self._thread_get_psutil_commandline)
        thread_get_psutil_commandline.daemon = True
        thread_get_psutil_commandline.start()

        thread_update_shared_dict = threading.Thread(target=self._update_shared_dict, args=(self.shared_dict_update_queue,))
        thread_update_shared_dict.daemon = True
        thread_update_shared_dict.start()

    def stop(self):
        self._running = False

    def get_processes(self):
        return self._processes

    def _start_main_thread(self, shared_dict_update_queue):
        get_instance = process_create.ProcessCreateSubscriber()
        get_instance.start()

        while self._running:
            event = get_instance.emit()
            process_id = event['NewProcessIdInt']
            process_name = Path(event['NewProcessName']).name
            command_line = event['CommandLine']

            # The event log tracing method doesn't always give the command line, unlike the psutil method.
            # So, we'll get the command line from the current psutil snapshot separately.
            if command_line == '':
                self.empty_cmdline_queue.put(process_id)

            self._processes[process_id] = {
                'name': process_name,
                'cmdline': command_line
            }

            # Update the multiprocessing shared dict proxy.
            shared_dict_update_queue.put(dict(self._processes))

    def _thread_get_psutil_commandline(self):
        """
        This function will get an entry from the queue where command line is missing and get the command line
        from the psutil snapshot.
        """

        while self._running:
            empty_cmd_pid = self.empty_cmdline_queue.get()
            current_psutil_process_snapshot: dict = get_process_list.GetProcessList(
                get_method='psutil', connect_on_init=True).get_processes(as_dict=True)
            command_line = current_psutil_process_snapshot[empty_cmd_pid]['cmdline']

            self._processes[empty_cmd_pid]['cmdline'] = command_line

            # Update the multiprocessing shared dict proxy.
            self.shared_dict_update_queue.put(dict(self._processes))

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

        self.shared_dict_update_queue.put(dict(self._processes))

    def _update_shared_dict(self, shared_dict_update_queue):
        while self._running:
            current_process_pool = shared_dict_update_queue.get()
            if self.process_pool_shared_dict_proxy is not None:
                self.process_pool_shared_dict_proxy.clear()
                self.process_pool_shared_dict_proxy.update(current_process_pool)


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

        self.get_process_with_psutil = get_process_list.GetProcessList(get_method='psutil', connect_on_init=True)

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
            # We need it so that the pool will not change in the middle of the process.
            current_pid_pool = convert_proxy_dict_to_dict(self.process_pool_shared_dict_proxy)
            if pid not in current_pid_pool:
                # print(dict(self.process_pool_shared_dict_proxy))
                time.sleep(0.1)
                counter += 1
            else:
                process_dict = current_pid_pool[pid]
                break

        if not process_dict:
            print_api(f"Error: The PID [{pid}] is not in the pool, trying psutil snapshot.", color='yellow')
            # Last resort, try to get the process name by current process snapshot.
            processes = self.get_process_with_psutil.get_processes(as_dict=True)
            if pid not in processes:
                print_api(f"Error: Couldn't get the process name for PID: {pid}.", color='red')
                process_dict = {
                    'name': pid,
                    'cmdline': ''
                }
            else:
                process_dict = processes[pid]

        return process_dict


def convert_proxy_dict_to_dict(proxy_dict: multiprocessing.managers.DictProxy) -> dict:
    """
    Convert the multiprocessing shared dict proxy to a normal dict.

    :param proxy_dict: multiprocessing.managers.DictProxy, the shared dict proxy.
    :return: dict, the normal dict.
    """

    # Create a snapshot of the keys
    keys = list(proxy_dict.keys())
    current_pid_pool = {}

    for key in keys:
        try:
            # Attempt to retrieve the value for each key
            current_pid_pool[key] = proxy_dict[key]
        except KeyError:
            # The key was removed concurrently; skip it
            continue

    return current_pid_pool
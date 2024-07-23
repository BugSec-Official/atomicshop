from typing import Union, Literal
import threading
import time

from ... import get_process_list


class PollerPsutilPywin32Dll:
    """
    The class is responsible for getting the list of opened processes by using mentioned libraries.
    """
    def __init__(
            self,
            interval_seconds: Union[int, float] = 0,
            process_get_method: Literal[
                'poll_psutil',
                'poll_pywin32',
                'poll_process_dll'
            ] = 'poll_process_dll',
            process_queue=None
    ):
        """
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
        :param process_queue: Queue. The queue to put the processes in. If None, the processes will not be put in the
            queue.
        """

        self.interval_seconds: Union[int, float] = interval_seconds
        self.process_get_method = process_get_method.replace('poll_', '')
        self.process_queue = process_queue

        # noinspection PyTypeChecker
        self.poller_instance = get_process_list.GetProcessList(get_method=self.process_get_method)

        self._processes = {}

    def start(self):
        """
        Start the poller.
        """

        thread = threading.Thread(target=self.emit_loop)
        thread.daemon = True
        thread.start()

    def emit_loop(self):
        """
        Get the list of processes.
        """

        self.poller_instance.connect()

        while True:
            current_processes = self.poller_instance.get_processes(as_dict=True)

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
                if pid in self._processes:
                    if self._processes[pid]['name'] == current_processes[pid]['name']:
                        if current_processes[pid]['cmdline'] == '':
                            current_processes[pid]['cmdline'] = self._processes[pid]['cmdline']
            self._processes.update(current_processes)

            self.process_queue.put(self._processes)

            time.sleep(self.interval_seconds)

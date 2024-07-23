import queue
import sys
import time
from typing import Literal

# Import FireEye Event Tracing library.
import etw

from ..print_api import print_api
from . import sessions
from ..process_poller import simple_process_pool
from ..wrappers.psutilw import psutilw


WAIT_FOR_PROCESS_POLLER_PID_SECONDS: int = 3
WAIT_FOR_PROCESS_POLLER_PID_COUNTS: int = WAIT_FOR_PROCESS_POLLER_PID_SECONDS * 10


class EventTrace(etw.ETW):
    def __init__(
            self,
            providers: list,
            event_callback=None,
            event_id_filters: list = None,
            session_name: str = None,
            close_existing_session_name: bool = True,
            enable_process_poller: bool = False
    ):
        """
        :param providers: List of tuples with provider name and provider GUID.
            tuple[0] = provider name
            tuple[1] = provider GUID
        :param event_callback: Reference to the callable callback function that will be called for each occurring event.
        :param event_id_filters: List of event IDs that we want to filter. If not provided, all events will be returned.
            The default in the 'etw.ETW' method is 'None'.
        :param session_name: The name of the session to create. If not provided, a UUID will be generated.
        :param close_existing_session_name: Boolean to close existing session names.
        :param enable_process_poller: Boolean to enable process poller. Gets the process PID, Name and CommandLine.
            Since the DNS events doesn't contain the process name and command line, only PID.
            Then DNS events will be enriched with the process name and command line from the process poller.

        ------------------------------------------

        You should stop the ETW tracing when you are done with it.
            'pywintrace' module starts a new session for ETW tracing, and it will not stop the session when the script
            exits or exception is raised.
            This can cause problems when you want to start the script again, and the session is already running.
            If the session is already running, and you start a new session with the same session name, you will get
            the buffer from when you stopped getting the events from the buffer.
            If you give different session name for new session, the previous session will still continue to run,
            filling the buffer with events, until you will stop getting new events on all sessions or get an
            exception that the buffer is full (WinError 1450).

            Example to stop the ETW tracing at the end of the script:
            from atomicshop.basics import atexits


            event_tracing = EventTrace(<Your parameters>)
            atexits.run_callable_on_exit_and_signals(EventTrace.stop)
        """
        self.event_queue = queue.Queue()
        self.close_existing_session_name: bool = close_existing_session_name
        self.enable_process_poller: bool = enable_process_poller

        # If no callback function is provided, we will use the default one, which will put the event in the queue.
        if not event_callback:
            function_callable = lambda x: self.event_queue.put(x)
        # If a callback function is provided, we will use it.
        else:
            function_callable = lambda x: event_callback(x)

        # Defining the list of specified ETW providers in 'etw' library format.
        etw_format_providers: list = list()
        for provider in providers:
            etw_format_providers.append(etw.ProviderInfo(provider[0], etw.GUID(provider[1])))

        if self.enable_process_poller:
            self.process_poller = simple_process_pool.SimpleProcessPool()

        super().__init__(
            providers=etw_format_providers, event_callback=function_callable, event_id_filters=event_id_filters,
            session_name=session_name
        )

    def start(self):
        if self.enable_process_poller:
            self.process_poller.start()

        # Check if the session name already exists.
        if sessions.is_session_running(self.session_name):
            print_api(f'ETW Session already running: {self.session_name}', color='yellow')

            # Close the existing session name.
            if self.close_existing_session_name:
                print_api(f'Closing existing session: {self.session_name}', color='blue')
                sessions.stop_and_delete(self.session_name)
            else:
                print_api(f'Using existing session: {self.session_name}', color='yellow')

        try:
            super().start()
        except OSError as e:
            message = f"PyWinTrace Error: {e}\n" \
                        f"PyWinTrace crashed, didn't find solution to this, RESTART computer."
            print_api(message, error_type=True, logger_method='critical')
            sys.exit(1)

    def stop(self):
        super().stop()

        if self.enable_process_poller:
            self.process_poller.stop()

    def emit(self):
        """
        The Function will return the next event from the queue.
        The queue is blocking, so if there is no event in the queue, the function will wait until there is one.

        Usage Example:
            while True:
                dns_dict = dns_trace.emit()
                print(dns_dict)

        event object:
            event[0]: is the event ID. Example: for DNS Tracing, it is event id 3008.
            event[1]: contains a dictionary with all the event's parameters.

        :return: etw event object.
        """

        # Get the processes first, since we need the process name and command line.
        # If they're not ready, we will get just pids from DNS tracing.
        if self.enable_process_poller:
            self._get_processes_from_poller()

        event: tuple = self.event_queue.get()

        event_dict: dict = {
            'EventId': event[0],
            'EventHeader': event[1],
            'pid': event[1]['EventHeader']['ProcessId']
        }

        if self.enable_process_poller:
            processes = self.process_poller.get_processes()
            if event_dict['pid'] not in processes:
                counter = 0
                while counter < WAIT_FOR_PROCESS_POLLER_PID_COUNTS:
                    processes = self.process_poller.get_processes()
                    if event_dict['pid'] not in processes:
                        time.sleep(0.1)
                        counter += 1
                    else:
                        break

                if counter == WAIT_FOR_PROCESS_POLLER_PID_COUNTS:
                    print_api(f"Error: Couldn't get the process name for PID: {event_dict['pid']}.", color='red')

            event_dict = psutilw.cross_single_connection_with_processes(event_dict, processes)

        return event_dict

    def _get_processes_from_poller(self):
        processes: dict = {}
        while not processes:
            processes = self.process_poller.get_processes()

            if isinstance(processes, BaseException):
                raise processes

        return processes

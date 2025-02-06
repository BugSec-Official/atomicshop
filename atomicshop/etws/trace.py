import queue
import sys
import time
import multiprocessing.managers

# Import FireEye Event Tracing library.
import etw

from ..print_api import print_api
from . import sessions
from ..process_poller import simple_process_pool
from ..wrappers.psutilw import psutilw


class EventTrace(etw.ETW):
    def __init__(
            self,
            providers: list,
            event_callback: callable = None,
            event_id_filters: list = None,
            session_name: str = None,
            close_existing_session_name: bool = True,
            enable_process_poller: bool = False,
            process_pool_shared_dict_proxy: multiprocessing.managers.DictProxy = None
    ):
        """
        :param providers: List of tuples with provider name and provider GUID.
            tuple[0] = provider name
            tuple[1] = provider GUID

            Example: [('Microsoft-Windows-DNS-Client', '{1c95126e-7ee8-4e23-86b2-6e7e4a5a8e9b}')]
        :param event_callback: Reference to the callable callback function that will be called for each occurring event.
        :param event_id_filters: List of event IDs that we want to filter. If not provided, all events will be returned.
            The default in the 'etw.ETW' method is 'None'.
        :param session_name: The name of the session to create. If not provided, a UUID will be generated.
        :param close_existing_session_name: Boolean to close existing session names.
        :param enable_process_poller: Boolean to enable process poller. Gets the process PID, Name and CommandLine.
            Since the DNS events doesn't contain the process name and command line, only PID.
            Then DNS events will be enriched with the process name and command line from the process poller.
        :param process_pool_shared_dict_proxy: multiprocessing.managers.DictProxy,
            multiprocessing shared dict proxy that contains current processes.
            Check the 'atomicshop\process_poller\simple_process_pool.py' SimpleProcessPool class for more information.

            If None, the process poller will create a new shared dict proxy.
            If provided, then the provided shared dict proxy will be used.
            Off course valid only if 'enable_process_poller' is True.

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
        self.process_pool_shared_dict_proxy: multiprocessing.managers.DictProxy = process_pool_shared_dict_proxy

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

        self.self_hosted_poller: bool = False
        if self.enable_process_poller:
            if self.process_pool_shared_dict_proxy is None:
                self.self_hosted_poller = True
                self.process_poller = simple_process_pool.SimpleProcessPool()
                self.multiprocessing_manager: multiprocessing.managers.SyncManager = multiprocessing.Manager()
                self.process_pool_shared_dict_proxy = self.multiprocessing_manager.dict()

            self.pid_process_converter = simple_process_pool.PidProcessConverter(
                process_pool_shared_dict_proxy=self.process_pool_shared_dict_proxy)

        super().__init__(
            providers=etw_format_providers, event_callback=function_callable, event_id_filters=event_id_filters,
            session_name=session_name
        )

    def start(self):
        if self.enable_process_poller and self.self_hosted_poller:
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

        if self.self_hosted_poller:
            self.process_poller.stop()

            self.multiprocessing_manager.shutdown()

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

        event: tuple = self.event_queue.get()

        event_dict: dict = {
            'EventId': event[0],
            'EventHeader': event[1]
        }

        if 'ProcessId' not in event[1]:
            event_dict['pid'] = event[1]['EventHeader']['ProcessId']
        else:
            event_dict['pid'] = event[1]['ProcessId']

        if self.enable_process_poller:
            process_info: dict = self.pid_process_converter.get_process_by_pid(event_dict['pid'])
            event_dict['name'] = process_info['name']
            event_dict['cmdline'] = process_info['cmdline']

        return event_dict

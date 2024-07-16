import queue
import sys

# Import FireEye Event Tracing library.
import etw

from ..print_api import print_api


class EventTrace(etw.ETW):
    def __init__(
            self,
            providers: list,
            event_callback=None,
            event_id_filters: list = None,
            session_name: str = None
    ):
        """
        :param providers: List of tuples with provider name and provider GUID.
            tuple[0] = provider name
            tuple[1] = provider GUID
        :param event_callback: Reference to the callable callback function that will be called for each occurring event.
        :param event_id_filters: List of event IDs that we want to filter. If not provided, all events will be returned.
            The default in the 'etw.ETW' method is 'None'.
        :param session_name: The name of the session to create. If not provided, a UUID will be generated.
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

        super().__init__(
            providers=etw_format_providers, event_callback=function_callable, event_id_filters=event_id_filters,
            session_name=session_name
        )

    def start(self):
        try:
            super().start()
        except OSError as e:
            message = f"PyWinTrace Error: {e}\n" \
                        f"PyWinTrace crashed, didn't find solution to this, RESTART computer."
            print_api(message, error_type=True, logger_method='critical')
            sys.exit(1)

    def stop(self):
        super().stop()

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

        return self.event_queue.get()


def find_sessions_by_provider(provider_name: str):
    """
    Find ETW session by provider name.

    :param provider_name: The name of the provider to search for.
    """

    return


def get_all_providers_from_session(session_name: str):
    """
    Get all providers that ETW session uses.

    :param session_name: The name of the session to get providers from.
    """

    return


def stop_session_by_name(session_name: str):
    """
    Stop ETW session by name.

    :param session_name: The name of the session to stop.
    """

    return

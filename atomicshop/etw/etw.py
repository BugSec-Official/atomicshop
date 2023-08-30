import queue

# Import FireEye Event Tracing library.
import etw


class EventTrace(etw.ETW):
    def __init__(self, providers: list, event_callback=None, event_id_filters: list = None):
        """
        :param providers: List of tuples with provider name and provider GUID.
            tuple[0] = provider name
            tuple[1] = provider GUID
        :param event_callback: Reference to the callable callback function that will be called for each occurring event.
        :param event_id_filters: List of event IDs that we want to filter. If not provided, all events will be returned.
            The default in the 'etw.ETW' method is 'None'.
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
            providers=etw_format_providers, event_callback=function_callable, event_id_filters=event_id_filters)

    def start(self):
        try:
            super().start()
        except OSError as e:
            raise OSError(f"PyWinTrace Error: {e}\n"
                          f"PyWinTrace crashed, didn't find solution to this, RESTART computer.")

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

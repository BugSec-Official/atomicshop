from . import trace
from .. import dns
from ..wrappers.psutilw import psutilw
from ..basics import dicts
from ..process_poller import ProcessPollerPool
from ..print_api import print_api


class DnsTrace:
    def __init__(
            self,
            enable_process_poller: bool = False,
            attrs: list = None,
            session_name: str = None,
            close_existing_session_name: bool = True
    ):
        """
        DnsTrace class use to trace DNS events from Windows Event Tracing for EventId 3008.

        :param enable_process_poller: Boolean to enable process poller. Gets the process PID, Name and CommandLine,
            every 100 ms. Since the DNS events doesn't contain the process name and command line, only PID.
            Then DNS events will be enriched with the process name and command line from the process poller.
        :param attrs: List of attributes to return. If None, all attributes will be returned.
        :param session_name: The name of the session to create. If not provided, a UUID will be generated.
        :param close_existing_session_name: Boolean to close existing session names.
            True: if ETW session with 'session_name' exists, you will be notified and the session will be closed.
                Then the new session with this name will be created.
            False: if ETW session with 'session_name' exists, you will be notified and the new session will not be
                created. Instead, the existing session will be used. If there is a buffer from the previous session,
                you will get the events from the buffer.

        -------------------------------------------------

        Usage Example:
            from atomicshop.etw import dns_trace


            dns_trace_w = dns_trace.DnsTrace(enable_process_poller=True, attrs=['pid', 'name', 'cmdline', 'domain', 'query_type'])
            dns_trace_w.start()
            while True:
                dns_dict = dns_trace_w.emit()
                print(dns_dict)
            dns_trace_w.stop()
        """

        self.enable_process_poller = enable_process_poller
        self.attrs = attrs

        self.event_trace = trace.EventTrace(
            providers=[(dns.ETW_DNS_INFO['provider_name'], dns.ETW_DNS_INFO['provider_guid'])],
            # lambda x: self.event_queue.put(x),
            event_id_filters=[dns.ETW_DNS_INFO['event_id']],
            session_name=session_name,
            close_existing_session_name=close_existing_session_name
        )

        if self.enable_process_poller:
            self.process_poller = ProcessPollerPool(store_cycles=200, operation='process', poller_method='process_dll')

    def start(self):
        if self.enable_process_poller:
            self.process_poller.start()

        self.event_trace.start()

    def stop(self):
        self.event_trace.stop()

        if self.enable_process_poller:
            self.process_poller.stop()

    def emit(self):
        """
        Function that will return the next event from the queue.
        The queue is blocking, so if there is no event in the queue, the function will wait until there is one.

        Usage Example:
            while True:
                dns_dict = dns_trace.emit()
                print(dns_dict)

        :return: Dictionary with the event data.
        """

        event = self.event_trace.emit()

        event_dict: dict = {
            'pid': event[1]['EventHeader']['ProcessId'],
            'etw_id': event[0],
            'domain': event[1]['QueryName'],
            'query_type_id': str(event[1]['QueryType']),
            'query_type': dns.TYPES_DICT[str(event[1]['QueryType'])]
        }

        # # Get process name only from psutil, just in case.
        # try:
        #     process_name = psutilw.get_process_name_by_pid(event_dict['pid'])
        # except psutil.NoSuchProcess:
        #     process_name = str(event_dict['pid'])

        # Defining list if ips and other answers, which aren't IPs.
        list_of_ips = list()
        list_of_other_domains = list()
        # Parse DNS results, only if 'QueryResults' key isn't empty, since many of the events are, mostly due errors.
        if event[1]['QueryResults']:
            # 'QueryResults' key contains a string with all the 'Answers' divided by type and ';' character.
            # Basically, we can parse each type out of string, but we need only IPs and other answers.
            list_of_parameters = event[1]['QueryResults'].split(';')

            # Iterating through all the parameters that we got from 'QueryResults' key.
            for parameter in list_of_parameters:
                # If 'type' string is present it means that entry is a domain;
                if 'type' in parameter:
                    # Remove the 'type' string and get the domain name.
                    current_iteration_parameter = parameter.rsplit(' ', maxsplit=1)[1]
                    # Add the variable to the list of other answers.
                    list_of_other_domains.append(current_iteration_parameter)
                # If 'type' string is not present it means that entry is an IP.
                else:
                    # Sometimes the last parameter in the 'QueryResults' key after ';' character will be empty, skip it.
                    if parameter:
                        list_of_ips.append(parameter)

        event_dict['ips'] = list_of_ips
        event_dict['other_domains'] = list_of_other_domains

        # Getting the 'QueryStatus' key.
        event_dict['status_id'] = event[1]['QueryStatus']

        # Getting the 'QueryStatus' key. If DNS Query Status is '0' then it was executed successfully.
        # And if not, it means there was an error. The 'QueryStatus' indicate what number of an error it is.
        if event[1]['QueryStatus'] == '0':
            event_dict['status'] = 'Success'
        else:
            event_dict['status'] = 'Error'

        if self.enable_process_poller:
            processes = self.process_poller.processes

            if isinstance(processes, BaseException):
                raise processes

            event_dict = psutilw.cross_single_connection_with_processes(event_dict, processes)
            # If it was impossible to get the process name from the process poller, get it from psutil.
            # if event_dict['name'].isnumeric():
            #     event_dict['name'] = process_name

        if self.attrs:
            event_dict = dicts.reorder_keys(
                event_dict, self.attrs, skip_keys_not_in_list=True)

        return event_dict

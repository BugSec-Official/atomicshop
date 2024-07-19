import time

from .. import trace, const
from ...wrappers.psutilw import psutilw
from ...basics import dicts
from ...process_poller import ProcessPollerPool
from ...print_api import print_api
from ... import dns


ETW_DEFAULT_SESSION_NAME: str = 'AtomicShopDnsTrace'

PROVIDER_NAME: str = const.ETW_DNS['provider_name']
PROVIDER_GUID: str = const.ETW_DNS['provider_guid']
REQUEST_RESP_EVENT_ID: int = const.ETW_DNS['event_ids']['dns_request_response']

WAIT_FOR_PROCESS_POLLER_PID_SECONDS: int = 3
WAIT_FOR_PROCESS_POLLER_PID_COUNTS: int = WAIT_FOR_PROCESS_POLLER_PID_SECONDS * 10


class DnsRequestResponseTrace:
    def __init__(
            self,
            attrs: list = None,
            session_name: str = None,
            close_existing_session_name: bool = True,
            enable_process_poller: bool = False,
            process_poller_etw_session_name: str = None
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
        :param process_poller_etw_session_name: The name of the ETW session for tracing process creation.

        -------------------------------------------------

        Usage Example:
            from atomicshop.etw import dns_trace


            dns_trace_w = dns_trace.DnsTrace(
                attrs=['pid', 'name', 'cmdline', 'domain', 'query_type'],
                session_name='MyDnsTrace',
                close_existing_session_name=True,
                enable_process_poller=True,
                process_poller_etw_session_name='MyProcessTrace'
            )
            dns_trace_w.start()
            while True:
                dns_dict = dns_trace_w.emit()
                print(dns_dict)
            dns_trace_w.stop()
        """

        self.enable_process_poller = enable_process_poller
        self.attrs = attrs

        if not session_name:
            session_name = ETW_DEFAULT_SESSION_NAME

        self.event_trace = trace.EventTrace(
            providers=[(PROVIDER_NAME, PROVIDER_GUID)],
            # lambda x: self.event_queue.put(x),
            event_id_filters=[REQUEST_RESP_EVENT_ID],
            session_name=session_name,
            close_existing_session_name=close_existing_session_name
        )

        if self.enable_process_poller:
            self.process_poller = ProcessPollerPool(
                operation='process', poller_method='sysmon_etw',
                sysmon_etw_session_name=process_poller_etw_session_name)

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

        # Get the processes first, since we need the process name and command line.
        # If they're not ready, we will get just pids from DNS tracing.
        if self.enable_process_poller:
            self._get_processes_from_poller()

        event = self.event_trace.emit()

        event_dict: dict = {
            'pid': event[1]['EventHeader']['ProcessId'],
            'etw_id': event[0],
            'domain': event[1]['QueryName'],
            'query_type_id': str(event[1]['QueryType']),
            'query_type': dns.TYPES_DICT[str(event[1]['QueryType'])]
        }

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
            # If it was impossible to get the process name from the process poller, get it from psutil.
            # if event_dict['name'].isnumeric():
            #     event_dict['name'] = process_name

        if self.attrs:
            event_dict = dicts.reorder_keys(
                event_dict, self.attrs, skip_keys_not_in_list=True)

        return event_dict

    def _get_processes_from_poller(self):
        processes: dict = {}
        while not processes:
            processes = self.process_poller.get_processes()

            if isinstance(processes, BaseException):
                raise processes

        return processes

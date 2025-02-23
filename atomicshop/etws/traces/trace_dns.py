import multiprocessing.managers

from .. import trace, const
from ...basics import dicts
from ... import dns, ip_addresses


ETW_DEFAULT_SESSION_NAME: str = 'AtomicShopDnsTrace'

PROVIDER_NAME: str = const.ETW_DNS['provider_name']
PROVIDER_GUID: str = const.ETW_DNS['provider_guid']
REQUEST_RESP_EVENT_ID: int = const.ETW_DNS['event_ids']['dns_request_response']


class DnsRequestResponseTrace:
    """DnsTrace class use to trace DNS events from Windows Event Tracing for EventId 3008."""
    def __init__(
            self,
            attrs: list = None,
            session_name: str = None,
            close_existing_session_name: bool = True,
            skip_record_list: list = None,
            process_pool_shared_dict_proxy: multiprocessing.managers.DictProxy = None
    ):
        """
        :param attrs: List of attributes to return. If None, all attributes will be returned.
        :param session_name: The name of the session to create. If not provided, a UUID will be generated.
        :param close_existing_session_name: Boolean to close existing session names.
            True: if ETW session with 'session_name' exists, you will be notified and the session will be closed.
                Then the new session with this name will be created.
            False: if ETW session with 'session_name' exists, you will be notified and the new session will not be
                created. Instead, the existing session will be used. If there is a buffer from the previous session,
                you will get the events from the buffer.
        :param skip_record_list: List of DNS Records to skip emitting. Example: ['PTR', 'SRV']
        :param process_pool_shared_dict_proxy: multiprocessing.managers.DictProxy, multiprocessing shared dict proxy
            that contains current processes.
            Check the 'atomicshop\process_poller\simple_process_pool.py' SimpleProcessPool class for more information.

            For this specific class it means that you can run the process poller outside of this class and pass the
            'process_pool_shared_dict_proxy' to this class. Then you can get the process name and command line for
            the DNS events from the 'process_pool_shared_dict_proxy' and use it also in other classes.

        -------------------------------------------------

        Usage Example:
            from atomicshop.etw import dns_trace


            dns_trace_w = dns_trace.DnsTrace(
                attrs=['pid', 'name', 'cmdline', 'query', 'query_type'],
                session_name='MyDnsTrace',
                close_existing_session_name=True,
                enable_process_poller=True
            )
            dns_trace_w.start()
            while True:
                dns_dict = dns_trace_w.emit()
                print(dns_dict)
            dns_trace_w.stop()
        """

        self.attrs = attrs
        self.process_pool_shared_dict_proxy: multiprocessing.managers.DictProxy = process_pool_shared_dict_proxy

        if skip_record_list:
            self.skip_record_list: list = skip_record_list
        else:
            self.skip_record_list: list = list()

        if not session_name:
            session_name = ETW_DEFAULT_SESSION_NAME

        self.event_trace = trace.EventTrace(
            providers=[(PROVIDER_NAME, PROVIDER_GUID)],
            # lambda x: self.event_queue.put(x),
            event_id_filters=[REQUEST_RESP_EVENT_ID],
            session_name=session_name,
            close_existing_session_name=close_existing_session_name,
            enable_process_poller=True,
            process_pool_shared_dict_proxy=self.process_pool_shared_dict_proxy
        )

    def start(self):
        self.event_trace.start()

    def stop(self):
        self.event_trace.stop()

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

        # Get the event from ETW as is.
        event = self.event_trace.emit()

        # Get the raw query results string from the event.
        query_results: str = event['EventHeader']['QueryResults']

        if query_results != '':
            query_results_list: list = query_results.split(';')

            addresses_ips: list = list()
            addresses_cnames: list = list()
            for query_result in query_results_list:
                # If there is a type in the query result, it means it is a cname (domain).
                if 'type' in query_result:
                    query_result = query_result.split(' ')[-1]

                # But we'll still make sure that the query result is an IP address or not.
                if ip_addresses.is_ip_address(query_result):
                    addresses_ips.append(query_result)
                # If it is not empty, then it is a cname.
                elif query_result != '':
                    addresses_cnames.append(query_result)
        # if the query results are empty, then we'll just set the addresses to empty lists.
        else:
            addresses_ips: list = list()
            addresses_cnames: list = list()

        status_id: str = str(event['EventHeader']['QueryStatus'])

        # Getting the 'QueryStatus' key. If DNS Query Status is '0' then it was executed successfully.
        # And if not, it means there was an error. The 'QueryStatus' indicate what number of an error it is.
        if status_id == '0':
            status = 'Success'
        else:
            status = 'Error'

        event_dict: dict = {
            'timestamp': event['timestamp'],
            'event_id': event['EventId'],
            'query': event['EventHeader']['QueryName'],
            'query_type_id': str(event['EventHeader']['QueryType']),
            'query_type': dns.TYPES_DICT[str(event['EventHeader']['QueryType'])],
            'result_ips': ','.join(addresses_ips),
            'result_cnames': ','.join(addresses_cnames),
            'status_id': status_id,
            'status': status,
            'pid': event['pid'],
            'name': event['name'],
            'cmdline': event['cmdline']
        }

        # Skip emitting the record if it is in the 'skip_record_list'.
        # Just recall the function to get the next event and return it.
        if event_dict['query_type'] in self.skip_record_list:
            return self.emit()

        if self.attrs:
            event_dict = dicts.reorder_keys(
                event_dict, self.attrs, skip_keys_not_in_list=True)

        return event_dict

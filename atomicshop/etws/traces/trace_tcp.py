import multiprocessing.managers

from .. import trace, const, providers
from ...basics import dicts
from ... import dns, ip_addresses


ETW_DEFAULT_SESSION_NAME: str = 'AtomicShopTcpTrace'

PROVIDER_NAME: str = "Microsoft-Windows-TCPIP"
PROVIDER_GUID: str = '{' + providers.get_provider_guid_by_name(PROVIDER_NAME) + '}'
REQUEST_RESP_EVENT_ID: int = 1033


class TcpIpNewConnectionsTrace:
    """
    TcpIpNewConnectionsTrace class use to trace new connection events from Windows Event Tracing:
    Provider: Microsoft-Windows-TCPIP
    EventId: 1033
    """
    def __init__(
            self,
            attrs: list = None,
            session_name: str = None,
            close_existing_session_name: bool = True,
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
        :param process_pool_shared_dict_proxy: multiprocessing.managers.DictProxy, multiprocessing shared dict proxy
            that contains current processes.
            Check the 'atomicshop\process_poller\simple_process_pool.py' SimpleProcessPool class for more information.

            For this specific class it means that you can run the process poller outside of this class and pass the
            'process_pool_shared_dict_proxy' to this class. Then you can get the process name and command line for
            the DNS events from the 'process_pool_shared_dict_proxy' and use it also in other classes.

        -------------------------------------------------

        Usage Example:
            from atomicshop.etw import tcp_trace


            tcp_trace_w = tcp_trace.TcpIpNewConnectionsTrace(
                attrs=['pid', 'name', 'cmdline', 'domain', 'query_type'],
                session_name='MyTcpTrace',
                close_existing_session_name=True,
                enable_process_poller=True
            )
            tcp_trace_w.start()
            while True:
                tcp_dict = tcp_trace_w.emit()
                print(tcp_dict)
            tcp_trace_w.stop()
        """

        self.attrs = attrs
        self.process_pool_shared_dict_proxy: multiprocessing.managers.DictProxy = process_pool_shared_dict_proxy

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
                tcp_dict = tcp_trace.emit()
                print(tcp_dict)

        :return: Dictionary with the event data.
        """

        # Get the event from ETW as is.
        event = self.event_trace.emit()

        local_address_port: str = event['EventHeader']['LocalAddress']
        remote_address_port: str = event['EventHeader']['RemoteAddress']

        if 'ffff' in local_address_port:
            pass

        local_address, local_port = local_address_port.rsplit(':', 1)
        local_address = local_address.replace('[', '').replace(']', '')

        remote_address, remote_port = remote_address_port.rsplit(':', 1)
        remote_address = remote_address.replace('[', '').replace(']', '')

        event_dict: dict = {
            'event_id': event['EventId'],
            'local_ip': local_address,
            'local_port': local_port,
            'remote_ip': remote_address,
            'remote_port': remote_port,
            'status': event['EventHeader']['Status'],
            'pid': event['pid'],
            'name': event['name'],
            'cmdline': event['cmdline']
        }

        if self.attrs:
            event_dict = dicts.reorder_keys(
                event_dict, self.attrs, skip_keys_not_in_list=True)

        return event_dict

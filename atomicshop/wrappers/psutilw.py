import shlex
import types

from ..basics import dicts, list_of_dicts
from ..print_api import print_api

import psutil


def get_network_interfaces() -> list:
    """
    The function will return list of all network interfaces.

    :return: list.
    """

    return list(psutil.net_if_addrs().items())


def get_available_process_attrs(self) -> list:
    """
    The function will return list of all available process attributes.

    :return: list.
    """

    return list(psutil.Process().as_dict().keys())


def _initialize_processes_for_conversion(processes) -> object:
    """
    Auxiliary function that will initialize 'processes' for conversion.

    :param processes: iterable object: 'list', 'set', 'frozenset', 'generator' result of 'psutil.process_iter()'.
        If it is a 'generator', it will be converted to 'list'.
    :return: iterable object: 'list', 'set', 'frozenset'.
    """

    # Check if 'processes' is iterable of supported types.
    if not isinstance(processes, frozenset) and not isinstance(processes, set) and \
            not isinstance(processes, list) and not isinstance(processes, types.GeneratorType):
        raise TypeError(f'[processes] must be list, frozenset, set or generator, not {type(processes)}')

    # If 'processes' is 'generator', convert it to 'list'.
    if isinstance(processes, types.GeneratorType):
        processes = list(processes)

    return processes


def convert_single_process_to_dict(process, cmdline_to_string: bool = False) -> dict:
    """
    The function will convert 'psutil.Process' object to dict.

    :param process: 'psutil.Process' object.
    :param cmdline_to_string: bool, if True, will convert 'cmdline' to string, using 'shlex.join'.
    :return: dict.
    """

    # Check if 'info' property doesn't exist.
    if 'info' not in process.__dict__:
        # Then convert 'process' to dict, by calling 'as_dict()' method of 'psutil'.
        process_dict = process.as_dict()
    # If 'info' property exists, it means the command was called with attributes list:
    # 'psutil.process_iter(some_keys_list)'.
    else:
        process_dict = process.info

    # If 'cmdline_to_string' is True, convert 'cmdline' to string.
    if cmdline_to_string:
        # 'cmdline' can be 'None' or empty list. So, we need to check it and fill accordingly.
        if process_dict['cmdline']:
            # Get cmdline as string.
            process_dict['cmdline'] = shlex.join(process.info['cmdline'])
        else:
            process_dict['cmdline'] = str()

    return process_dict


def convert_processes_to_dict(processes, cmdline_to_string: bool = False) -> dict:
    """
    The function will get any iterable object that represents execution of 'psutil.process_iter()':
        'list', 'set', 'frozenset', 'generator'.
    and convert it to dict:
        {<pid: int>: {
            'name': <process_name: str>,
            'cmdline': <process_cmdline: str>
            etc...
        }}

    :param processes: iterable object: 'list', 'set', 'frozenset', 'generator' result of 'psutil.process_iter()'.
        Default: None, will use 'self.processes'.
    :param cmdline_to_string: bool, if True, will convert 'cmdline' to string, using 'shlex.join()'.
    :return: dict.
    """

    processes = _initialize_processes_for_conversion(processes)

    # Initialize dict.
    processes_dict: dict = dict()
    # Iterate through all the processes.
    for process in processes:
        process_dict = convert_single_process_to_dict(process, cmdline_to_string)

        # Fill current 'pid' key with process name and cmdline.
        processes_dict[process.pid] = dict()
        for key in process_dict.keys():
            if key != 'pid':
                processes_dict[process.pid][key] = process_dict[key]

    return processes_dict


def convert_processes_to_list_of_dicts(processes, cmdline_to_string: bool = False) -> list:
    """
    The function will get any iterable object that represents execution of 'psutil.process_iter()':
        'list', 'set', 'frozenset', 'generator'.
    and convert it to list of dicts.

    :param processes: iterable object: 'list', 'set', 'frozenset', 'generator' result of 'psutil.process_iter()'.
        Default: None, will use 'self.processes'.
    :param cmdline_to_string: bool, if True, will convert 'cmdline' to string, using 'shlex.join()'.
    :return: list of dicts.
    """

    processes = _initialize_processes_for_conversion(processes)

    # Initialize dict.
    processes_list: list = list()
    # Iterate through all the processes.
    for process in processes:
        process_dict = convert_single_process_to_dict(process, cmdline_to_string)
        processes_list.append(process_dict)

    return processes_list


def filter_processes_with_present_connections(processes) -> list:
    processes_with_present_connections: list = list()
    for process in processes:
        if 'connections' not in process.keys():
            continue
        elif not process['connections']:
            continue
        else:
            processes_with_present_connections.append(process)

    return processes_with_present_connections


class PsutilProcesses:
    def __init__(self):
        self.processes = None

    def get_processes(self, attrs: list = None, default_keys: bool = False, iterable_type: str = 'list') -> object:
        """
        The function should be executed under administrative privileges or 'cmdline' will return empty for
        system processes and services.

        :param attrs: list, equivalent to 'attrs' of 'psutil.process_iter'.
            Default: None, as in 'psutil.process_iter()'.
            The developers say that specifying 'attrs' will improve performance, since 'psutil' will need to retrieve
            less objects.
        :param default_keys: bool, if True, will return only attrs: pid, name, cmdline.
        :param iterable_type: str, the type of iterable to return. Available options:
            'list', 'set', 'frozenset', None.
            'None' will return 'psutil.process_iter' generator object as is.
        :return: iterable object or psutil.process_iter 'generator' object, of all the current psutil processes
            of "psutil.process_iter".
        """

        if default_keys:
            attrs = ['pid', 'name', 'cmdline']

        if iterable_type == 'list':
            self.processes = list(psutil.process_iter(attrs))
        elif iterable_type == 'set':
            self.processes = set(psutil.process_iter(attrs))
        elif iterable_type == 'frozenset':
            self.processes = frozenset(psutil.process_iter(attrs))
        elif iterable_type is None:
            self.processes = psutil.process_iter(attrs)
        else:
            raise TypeError(f'[iterable_type] must be "list", "set", "frozenset" or "None", not {iterable_type}')

        return self.processes

    def get_processes_as_dict(
            self, attrs: list = None, default_keys: bool = False, cmdline_to_string: bool = False) -> dict:
        """
        The function will return dict of all current processes.

        :param attrs: list, equivalent to 'attrs' of 'psutil.process_iter'.
            Default: None, as in 'psutil.process_iter()'.
            The developers say that specifying 'attrs' will improve performance, since 'psutil' will need to retrieve
            less objects.
        :param default_keys: bool, if True, will return only attrs: pid, name, cmdline.
        :param cmdline_to_string: bool, if True, will convert 'cmdline' to string, using 'shlex.join()'.
        :return: dict, of all the current psutil processes.
        """

        self.get_processes(attrs, default_keys)
        self.processes = convert_processes_to_dict(
            self.processes, cmdline_to_string=cmdline_to_string)
        return self.processes

    def get_processes_as_list_of_dicts(
            self, attrs: list = None, default_keys: bool = False, cmdline_to_string: bool = False) -> list:
        """
        The function will return list of all current processes.

        :param attrs: list, equivalent to 'attrs' of 'psutil.process_iter'.
            Default: None, as in 'psutil.process_iter()'.
            The developers say that specifying 'attrs' will improve performance, since 'psutil' will need to retrieve
            less objects.
        :param default_keys: bool, if True, will return only attrs: pid, name, cmdline.
        :param cmdline_to_string: bool, if True, will convert 'cmdline' to string, using 'shlex.join()'.
        :return: list of dicts, of all the current psutil processes.
        """

        self.get_processes(attrs, default_keys)
        self.processes = convert_processes_to_list_of_dicts(
            self.processes, cmdline_to_string=cmdline_to_string)
        return self.processes


def convert_single_connection_to_dict(connection, attrs: list = None) -> dict:
    """
    The function will get single connection object from 'psutil.net_connections(kind)' and convert it to dict:
        {
            'pid': connection.pid,
            'family': connection.family,
            'type': connection.type,
            'status': connection.status,
            'src_ip': connection.laddr.ip,
            'src_port': connection.laddr.port,
            'dst_ip': connection.raddr.ip,
            'dst_port': connection.raddr.port,
        }

    :param connection: single connection object.
    :param attrs: list, will return only the specified attributes of 'connection' object from
        'psutil.net_connections(kind)'.
    :return: dict.
    """

    # If 'laddr' tuple is populated.
    if connection.laddr:
        src_dict = {'src_ip': str(connection.laddr.ip), 'src_port': str(connection.laddr.port)}
    # If 'laddr' tuple is empty.
    else:
        src_dict = {'src_ip': str(), 'src_port': str()}

    # If 'raddr' tuple is populated.
    if connection.raddr:
        dst_dict = {'dst_ip': str(connection.raddr.ip), 'dst_port': str(connection.raddr.port)}
    # If 'raddr' tuple is empty.
    else:
        dst_dict = {'dst_ip': str(), 'dst_port': str()}

    # Assign variables to dict.
    connection_dict: dict = dict()

    # This function can also be used against connections inside processes, they don't have 'pid' attribute.
    try:
        connection_dict['pid'] = connection.pid
    except AttributeError:
        pass

    connection_dict.update({
        'family': str(connection.family),
        'type': str(connection.type),
        'status': str(connection.status),
        'src_ip': src_dict['src_ip'],
        'src_port': src_dict['src_port'],
        'dst_ip': dst_dict['dst_ip'],
        'dst_port': dst_dict['dst_port']
    })

    result_dict: dict = dict()
    # If 'attrs' is specified.
    if attrs:
        # Add only specified attributes to the new dict.
        result_dict = dicts.reorder_keys(connection_dict, attrs, skip_keys_not_in_list=True)
    # If 'attrs' is not specified.
    else:
        # Add all attributes to the new dict as is.
        result_dict = connection_dict

    return result_dict


def convert_connections_to_list_of_dicts(
        connections: list, attrs: list = None, skip_empty_dst: bool = False) -> list:
    """
    The function will get list result of "psutil.net_connections(kind)" and convert it to dict:
        {
            'pid': connection.pid,
            'family': connection.family,
            'type': connection.type,
            'status': connection.status,
            'src_ip': connection.laddr.ip,
            'src_port': connection.laddr.port,
            'dst_ip': connection.raddr.ip,
            'dst_port': connection.raddr.port,
        }

    :param connections: list, that contains result of "psutil.net_connections(kind)".
    :param attrs: list, will return only the specified attributes of 'connections' object.
    :param skip_empty_dst: bool, if True, will skip connections with empty 'dst_ip' and 'dst_port' keys.
    :return: dict.
    """

    # Initialize list.
    connections_list_of_dicts: list = list()
    # Iterate through all the connections.
    for connection in connections:
        # If 'destination' is empty and 'skip_empty_dst' is 'True' - skip current connection.
        if skip_empty_dst and not connection.raddr:
            continue

        result_dict = convert_single_connection_to_dict(connection, attrs)

        # And append to list.
        connections_list_of_dicts.append(result_dict)

    return connections_list_of_dicts


class PsutilConnections:
    def __init__(self):
        self.connections = None

    def get_connections(self, kind: str = 'all') -> list:
        """
        The function will return all current connections.

        :param kind: string, equivalent to 'kind' of 'psutil.net_connections'.
            Default: 'all', which is not the default in 'psutil.net_connections'.
        :return: list, of "psutil.net_connections". Returned by default as 'list'.
        """

        self.connections = psutil.net_connections(kind)
        return self.connections

    def get_connections_as_list_of_dicts(self, attrs: list = None, skip_empty_dst: bool = False):
        """
        The function will return list of dicts, containing all current connections.

        :return: list of dicts.
        """

        self.get_connections()
        self.connections = convert_connections_to_list_of_dicts(
            connections=self.connections, attrs=attrs, skip_empty_dst=skip_empty_dst)
        return self.connections

    def get_connections_with_process_as_list_of_dicts(
            self, attrs: list = None, skip_empty_dst: bool = False, cmdline_to_string: bool = False,
            sort_by_keys: list = None, case_insensitive: bool = False, remove_duplicates: bool = False):
        """
        The function will return list of dicts, containing all current connections and process info.
        It uses 'PsutilProcesses' class to get the process info, which is executed as:
            processes.get_processes_as_list_of_dicts(attrs=['pid', 'name', 'cmdline', 'connections'])
        to get the process info with connections.

        :param attrs: list, will return only the specified attributes of 'connection' object from
            'psutil.process_iter(attrs=['pid', 'name', 'cmdline', 'connections'])'.
        :param skip_empty_dst: bool, if True, will skip connections with empty 'dst_ip' and 'dst_port' keys.
        :param cmdline_to_string: bool, if True, will convert 'cmdline' to string.
        :param sort_by_keys: list, will sort the result by specified keys.
        :param case_insensitive: bool, if True, will sort the result case-insensitive.
        :param remove_duplicates: bool, if True, will remove duplicates from the result.
        :return: list of dicts.
        """

        processes = PsutilProcesses()
        processes_with_connections: list = processes.get_processes_as_list_of_dicts(
            attrs=['pid', 'name', 'cmdline', 'connections'], cmdline_to_string=cmdline_to_string)

        # Get only processes with present connections.
        processes_with_present_connections: list = filter_processes_with_present_connections(
            processes_with_connections)

        # Iterate through all the processes with present connections.
        connections_with_processes: list = list()
        for process in processes_with_present_connections:
            # Iterate through all the connections of the current process.
            for connection in process['connections']:
                # If 'destination' is empty and 'skip_empty_dst' is 'True' - skip current connection.
                if skip_empty_dst and not connection.raddr:
                    continue

                # Get the 'name' and 'cmdline' by 'pid' to dict.
                connection_dict = convert_single_connection_to_dict(connection)

                # Create new dict with 'name', 'cmdline' and 'pid' to the connection dict.
                connection_dict_with_process: dict = {
                    'name': process['name'],
                    'cmdline': process['cmdline'],
                    'pid': process['pid']
                }
                # Add 'connection' dict to the new dict.
                connection_dict_with_process.update(connection_dict)
                # Reorder keys and add only specified attributes to the new dict.
                connection_dict_with_process = dicts.reorder_keys(
                    connection_dict_with_process, attrs, skip_keys_not_in_list=True)

                # And append to list.
                connections_with_processes.append(connection_dict_with_process)

        # Remove duplicates.
        if remove_duplicates:
            connections_with_processes = list_of_dicts.remove_duplicates(connections_with_processes)

        # Sort by specified keys.
        if sort_by_keys:
            connections_with_processes = list_of_dicts.sort_by_keys(
                connections_with_processes, sort_by_keys, case_insensitive=case_insensitive)

        self.connections = connections_with_processes
        return self.connections


def cross_single_connection_with_processes(connection: dict, processes: dict) -> dict:
    """
    The function will take the output of 'convert_processes_to_dict' and single dict of
    'convert_connections_to_list_of_dicts' functions and cross it to make dict of connection containing
    proper process 'name' and 'cmdline'.

    :param processes: dict, result of 'convert_processes_to_dict'.
    :param connection: dict, single result of 'convert_connections_to_list_of_dicts'.
    :return: dict.
    """

    # Get the 'name' and 'cmdline' by 'pid' to dict. 'connection' is current iteration, where 'pid' is not
    # removed.
    # try:
    connection_process_dict = processes[connection['pid']].copy()
    # except KeyError:
    #     connection_process_dict = {
    #         'name': str(connection['pid']),
    #         'cmdline': str()
    #     }

    # We want 'name' and 'cmdline' to be first in the dict, so we'll append what is left of current iteration.
    connection_process_dict.update(connection)

    return connection_process_dict


def cross_connections_and_processes(connections: list, processes: dict, **kwargs) -> None:
    """
    The function will take the output of 'convert_processes_to_dict' and 'convert_connections_to_list_of_dicts'
    functions and cross it to make list of dicts of connections containing proper process 'name' and 'cmdline'.

    Since list is a class instance, we don't need to return it, since it happens inplace.

    :param connections: list, result of 'convert_connections_to_list_of_dicts'.
    :param processes: dict, result of 'convert_processes_to_dict'.
    :return: None.
    """

    i = 0
    count = len(connections)

    while i < count:
        try:
            # Assign the updated dict to current iteration.
            connections[i] = cross_single_connection_with_processes(processes, connections[i])
        except KeyError:
            # If there is no 'pid' in 'processes' dict, it means that the process is already dead.
            # This happens because the process ended and connection turned to 'CLOSING' state.
            # 'psutil' shows this as 'new' connection, because this is how it works when connection state is changing,
            # but it is not a new connection.
            message = f'PID [{connections[i]["pid"]}] is terminated, connection is terminating. Skipping...'
            print_api(message, error_type=True, **kwargs)
            # Remove current iteration from list.
            del connections[i]
            # Decrement the count.
            count -= 1
            # Skip the increment.
            continue

        i += 1

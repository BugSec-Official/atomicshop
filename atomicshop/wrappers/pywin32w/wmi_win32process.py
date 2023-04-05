import win32com.client
import pythoncom


def convert_single_process_to_dict(process, attrs: list = None) -> dict:
    """
    The function will convert pywin32 WMI COM object of Win32_Process to dict.

    :param process: pywin32 WMI COM object of Win32_Process.
    :param attrs: list of attributes to get from the process. Faster than getting all the attributes.
    :return: dict.
    """

    # Initialize dict.
    process_dict: dict = dict()

    # If 'attrs' wasn't provided, iterate through all the attributes.
    if not attrs:
        # Iterate through all the properties of the process.
        for property in process.Properties_:
            # Get property name.
            property_name = property.Name
            # Get property value.
            property_value = property.Value

            # Sometimes properties are None, so we need to convert them to str.
            if property_value is None:
                property_value = str()

            # Fill current 'pid' key with process name and cmdline.
            process_dict[property_name] = property_value
    # If 'attrs' was provided, iterate through the provided attributes.
    else:
        # Iterate through all the attributes.
        for attr in attrs:
            # Get property value.
            property_value = getattr(process, attr)

            # Sometimes properties are None, so we need to convert them to str.
            if property_value is None:
                property_value = str()

            # Fill current 'pid' key with process name and cmdline.
            process_dict[attr] = property_value

    return process_dict


def convert_processes_to_dict(processes, attrs: list = None) -> dict:
    """
    The function will get a list that represents result of pywin32 COM query of WMI Win32_Process
    and convert it to dict:
        {<ProcessId: int>: {
            'Name': <process_name: str>,
            'CommandLine': <process_cmdline: str>
            etc...
        }}

    :param processes: list that represents result of pywin32 COM query of WMI Win32_Process.
    :param attrs: list of attributes to get from the process. Faster than getting all the attributes.
    :return: dict.
    """

    # Initialize dict.
    processes_dict: dict = dict()
    # Iterate through all the processes.
    for process in processes:
        process_dict = convert_single_process_to_dict(process, attrs)

        # Fill current 'pid' key with process name and cmdline.
        processes_dict[process_dict['ProcessId']] = dict()
        for key in process_dict.keys():
            if key != 'ProcessId':
                processes_dict[process_dict['ProcessId']][key] = process_dict[key]

    return processes_dict


def convert_processes_to_list_of_dicts(processes, attrs: list = None) -> list:
    """
    The function will get a list that represents result of pywin32 COM query of WMI Win32_Process
    and convert it to list of dicts.

    :param processes: list that represents result of pywin32 COM query of WMI Win32_Process.
    :param attrs: list of attributes to get from the process. Faster than getting all the attributes.
    :return: list of dicts.
    """

    # Initialize dict.
    processes_list: list = list()
    # Iterate through all the processes.
    for process in processes:
        process_dict = convert_single_process_to_dict(process, attrs)
        processes_list.append(process_dict)

    return processes_list


class Pywin32Processes:
    """
    The class is a wrapper for 'win32com.client' modules, which is polling 'Win32_Process' WMI class.
    Administrative privileges are required to query WMI.
    """
    def __init__(self, host_to_query: str = '.'):
        """
        :param host_to_query: str, the host to query. Default: '.' (local host).
        """
        self.host_to_query = host_to_query

        self.wmi_cim_root = None
        self.processes = None

    def connect(self):
        """
        Connect to WMI CIM root.
        If running in multithreaded/multiprocess environment, you need to call 'pythoncom.CoInitialize()'
        and 'connect' method should be executed inside the started thread/process and not before.
        """

        com_object_wmi_service = win32com.client.Dispatch("WbemScripting.SWbemLocator", pythoncom.CoInitialize())
        self.wmi_cim_root = com_object_wmi_service.ConnectServer(self.host_to_query, "root\cimv2")

    def get_processes(self) -> list:
        """
        Get all current processes.

        :return: list of WMI COM objects.
        """

        self.processes = list(self.wmi_cim_root.ExecQuery("SELECT * FROM Win32_Process"))

        return self.processes

    def get_processes_as_dict(
            self, attrs: list = None, default_keys: bool = False) -> dict:
        """
        The function will return dict of all current processes.

        :param attrs: list. Default: None, all properties of WMI Win32_Process will be returned.
        :param default_keys: bool, if True, will return only attrs: 'ProcessId', 'Name', 'CommandLine'.
        :return: dict, of all the current psutil processes.
        """

        self.get_processes()

        if default_keys:
            attrs = ['ProcessId', 'Name', 'CommandLine']

        self.processes = convert_processes_to_dict(self.processes, attrs)
        return self.processes

    def get_processes_as_list_of_dicts(
            self, attrs: list = None, default_keys: bool = False) -> list:
        """
        The function will return list of all current processes.

        :param attrs: list. Default: None, all properties of WMI Win32_Process will be returned.
        :param default_keys: bool, if True, will return only attrs: 'ProcessId', 'Name', 'CommandLine'.
        :return: list of dicts, of all the current WMI Win32_process processes.
        """

        self.get_processes()

        if default_keys:
            attrs = ['ProcessId', 'Name', 'CommandLine']

        self.processes = convert_processes_to_list_of_dicts(self.processes, attrs)
        return self.processes

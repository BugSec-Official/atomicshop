from typing import Union, Literal

from .wrappers.pywin32w.wmis import win32process
from .wrappers.psutilw import psutilw
from .basics import dicts
from . import get_process_name_cmd_dll


class GetProcessList:
    """
    The class is responsible for getting the list of running processes.

    Example of one time polling with 'pywin32' method:
    from atomicshop import process_poller
    process_list: dict = \
        process_poller.GetProcessList(get_method='pywin32', connect_on_init=True).get_processes(as_dict=True)
    """
    def __init__(
            self,
            get_method: Literal['psutil', 'pywin32', 'process_dll'] = 'process_dll',
            connect_on_init: bool = False
    ):
        """
        :param get_method: str, The method to get the list of processes. Default is 'process_list_dll'.
            'psutil': Get the list of processes by 'psutil' library. Resource intensive and slow.
            'pywin32': Get the list of processes by 'pywin32' library, using WMI. Not resource intensive, but slow.
            'process_dll'. Not resource intensive and fast. Probably works only in Windows 10 x64.
        :param connect_on_init: bool, if True, will connect to the service on init. 'psutil' don't need to connect.
        """
        self.get_method = get_method
        self.process_polling_instance = None

        self.connected = False

        if self.get_method == 'psutil':
            self.process_polling_instance = psutilw.PsutilProcesses()
            self.connected = True
        elif self.get_method == 'pywin32':
            self.process_polling_instance = win32process.Pywin32Processes()
        elif self.get_method == 'process_dll':
            self.process_polling_instance = get_process_name_cmd_dll.ProcessNameCmdline()

        if connect_on_init:
            self.connect()

    def connect(self):
        """
        Connect to the service. 'psutil' don't need to connect.
        """

        # If poller method is none of the allowed methods.
        if self.get_method not in ['psutil', 'pywin32', 'process_dll']:
            raise ValueError(f"Method '{self.get_method}' is not allowed.")

        # If the service is not connected yet. Since 'psutil' don't need to connect.
        if not self.connected:
            if self.get_method == 'pywin32':
                self.process_polling_instance.connect()
                self.connected = True
            elif self.get_method == 'process_dll':
                self.process_polling_instance.load()
                self.connected = True

    def get_processes(self, as_dict: bool = True) -> Union[list, dict]:
        """
        The function will get the list of opened processes and return it as a list of dicts.

        :return: dict while key is pid or list of dicts, of opened processes (depending on 'as_dict' setting).
        """

        if as_dict:
            if self.get_method == 'psutil':
                return self.process_polling_instance.get_processes_as_dict(
                    attrs=['pid', 'name', 'cmdline'], cmdline_to_string=True)
            elif self.get_method == 'pywin32':
                processes = self.process_polling_instance.get_processes_as_dict(
                    attrs=['ProcessId', 'Name', 'CommandLine'])

                # Convert the keys from WMI to the keys that are used in 'psutil'.
                converted_process_dict = dict()
                for pid, process_info in processes.items():
                    converted_process_dict[pid] = dicts.convert_key_names(
                        process_info, {'Name': 'name', 'CommandLine': 'cmdline'})

                return converted_process_dict
            elif self.get_method == 'process_dll':
                return self.process_polling_instance.get_process_details(as_dict=True)
        else:
            if self.get_method == 'psutil':
                return self.process_polling_instance.get_processes_as_list_of_dicts(
                    attrs=['pid', 'name', 'cmdline'], cmdline_to_string=True)
            elif self.get_method == 'pywin32':
                processes = self.process_polling_instance.get_processes_as_list_of_dicts(
                    attrs=['ProcessId', 'Name', 'CommandLine'])

                # Convert the keys from WMI to the keys that are used in 'psutil'.
                for process_index, process_info in enumerate(processes):
                    processes[process_index] = dicts.convert_key_names(
                        process_info, {'ProcessId': 'pid', 'Name': 'name', 'CommandLine': 'cmdline'})

                return processes
            elif self.get_method == 'process_dll':
                return self.process_polling_instance.get_process_details(as_dict=as_dict)


def get_process_time_tester(
        get_method: Literal['psutil', 'pywin32', 'process_dll'] = 'process_dll',
        times_to_test: int = 50
):
    """
    The function will test the time it takes to get the list of processes with different methods and cycles.

    :param get_method: str, The method to get the list of processes. Default is 'process_list_dll'.
        'psutil': Get the list of processes by 'psutil' library. Resource intensive and slow.
        'pywin32': Get the list of processes by 'pywin32' library, using WMI. Not resource intensive, but slow.
        'process_dll'. Not resource intensive and fast. Probably works only in Windows 10 x64
    :param times_to_test: int, how many times to test the function.
    """

    import timeit

    setup_code = '''
from atomicshop import process_poller
get_process_list = process_poller.GetProcessList(get_method=get_method, connect_on_init=True)
'''

    test_code = '''
test = get_process_list.get_processes()
'''

    # globals need to be specified, otherwise the setup_code won't work with passed variables.
    times = timeit.timeit(setup=setup_code, stmt=test_code, number=times_to_test, globals=locals())
    print(f'Execution time: {times}')

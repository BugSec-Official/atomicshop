import pkg_resources
import ctypes
from ctypes import wintypes
from typing import Literal

from .basics import list_of_dicts


class ProcessNameCmdline:
    def __init__(self, load_dll: bool = False):
        self.load_dll: bool = load_dll
        self.dll_path: str = pkg_resources.resource_filename(
            __package__, 'addons/process_list/compiled/Win10x64/process_list.dll')
        self.dll = None
        self.callback_output = None
        self.CALLBACKFUNC = None

        if self.load_dll:
            self.load()

    def load(self):
        """
        Load the DLL, initialize the callback function and ctypes.
        ctypes.WINFUCNTYPE is not thread safe. You should load it inside a thread / process and not outside.
        """
        self.dll = ctypes.windll.LoadLibrary(self.dll_path)
        self.callback_output = OutputList()
        self.CALLBACKFUNC = ctypes.WINFUNCTYPE(None, wintypes.DWORD, wintypes.LPWSTR, wintypes.LPWSTR)

    def get_process_details(
            self,
            sort_by: Literal['pid', 'name', 'cmdline', None] = None,
            as_dict: bool = False,
    ):
        """
        :param sort_by: str, the key to sort the list of processes by. Default is None - Not to sort.
        :param as_dict: bool, if True, the 'pid' key will be converted to key of the dict and the whole list to a dict.
            Example:
                [
                    { 'pid': 123, 'name': 'some_name' },
                    { 'pid': 456, 'name': 'some_name2' }
                ]

                Converted to:
                {
                    123: { 'name': 'some_name' },
                    456: { 'name': 'some_name2' }
                }
        """

        self.dll.GetProcessDetails.argtypes = [self.CALLBACKFUNC]
        self.dll.GetProcessDetails(self.CALLBACKFUNC(self.callback_output.callback))

        processes = self.callback_output.data

        # Clear the callback output list, or it will be appended each time.
        self.callback_output.data = list()

        if sort_by:
            processes = list_of_dicts.sort_by_keys(processes, key_list=[sort_by])

        if as_dict:
            processes = convert_processes_to_dict(processes)

        return processes


def convert_processes_to_dict(process_list: dict) -> dict:
    """
    The function will convert the list of processes to dict, while 'pid' values will be converted to key.
    Example:
        { 'pid': 123, 'name': 'some_name' } -> { 123: { 'name': 'some_name' } }

    :param process_list: list of dicts of all the processes.
    :return: dict.
    """

    # Initialize dict.
    result_dict: dict = dict()

    for process in process_list:
        # Check if 'pid' key exists.
        if 'pid' not in process.keys():
            raise KeyError(f'[process_dict] must contain "pid" key, not {process.keys()}')

        # Fill current 'pid' key with process name and cmdline.
        result_dict[process['pid']] = dict()
        for key in process.keys():
            if key != 'pid':
                result_dict[process['pid']][key] = process[key]

    return result_dict


# Define a callback function for handling output from the DLL
class OutputList:
    def __init__(self):
        self.data: list = list()

    def callback(self, pid, process_name, cmdline):
        try:
            self.data.append({
                "pid": pid,
                "name": process_name.decode("utf-16"),
                "cmdline": cmdline.decode("utf-16") if cmdline else "Error"
            })
        except AttributeError:
            self.data.append({
                "pid": pid,
                "name": process_name,
                "cmdline": cmdline if cmdline else "Error"
            })

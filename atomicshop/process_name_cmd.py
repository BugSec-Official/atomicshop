from importlib.resources import files
import ctypes
from ctypes import wintypes
from typing import Literal
import threading

from .basics import list_of_dicts


PACKAGE_DLL_PATH = 'addons/process_list/compiled/Win10x64/process_list.dll'
FULL_DLL_PATH = str(files(__package__).joinpath(PACKAGE_DLL_PATH))


class ProcessNameCmdline:
    def __init__(self, load_dll: bool = False):
        self.load_dll: bool = load_dll
        self.dll_path = FULL_DLL_PATH

        self.dll = None
        self.callback_output = None
        self.CALLBACKFUNC = None
        self.CALLBACKFUNC_ref = None

        if self.load_dll:
            self.load()

    def load(self):
        """
        Load the DLL, initialize the callback function and ctypes.
        ctypes.WINFUNCTYPE is not thread safe. You should load it inside a thread / process and not outside.
        """
        self.dll = ctypes.windll.LoadLibrary(self.dll_path)
        self.callback_output = OutputList()
        self.CALLBACKFUNC = ctypes.WINFUNCTYPE(None, wintypes.DWORD, wintypes.LPWSTR, wintypes.LPWSTR)
        self.CALLBACKFUNC_ref = self.CALLBACKFUNC(self.callback_output.callback)

        # Set the argument types for the export functions of the DLL.
        self.dll.GetProcessDetails.argtypes = [self.CALLBACKFUNC]
        self.dll.RequestCancellation.restype = None

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

        def enumerate_process():
            self.dll.GetProcessDetails(self.CALLBACKFUNC_ref)

        thread = threading.Thread(target=enumerate_process)
        thread.start()

        try:
            # This is needed to stop the thread if the main thread is interrupted.
            # If we execute the 'self.dll.GetProcessDetails(self.CALLBACKFUNC_ref)' directly
            # and we would like to KeyboardInterrupt, we will get an error:
            # Exception ignored on calling ctypes callback function.
            thread.join()

            processes = self.callback_output.data

            # Clear the callback output list, or it will be appended each time.
            self.callback_output.data = list()

            if sort_by:
                processes = list_of_dicts.sort_by_keys(processes, key_list=[sort_by])

            if as_dict:
                processes = convert_processes_to_dict(processes)

            return processes
        except KeyboardInterrupt:
            self.dll.RequestCancellation()
            raise


def convert_processes_to_dict(process_list: list[dict]) -> dict:
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
            process_name_decoded = process_name.decode("utf-16") if isinstance(process_name, bytes) else process_name
            cmdline_decoded = cmdline.decode("utf-16") if isinstance(cmdline, bytes) else (
                cmdline if cmdline else "Error")
            self.data.append({
                "pid": pid,
                "name": process_name_decoded,
                "cmdline": cmdline_decoded
            })
        # except AttributeError:
        #     self.data.append({
        #         "pid": pid,
        #         "name": process_name,
        #         "cmdline": cmdline if cmdline else "Error"
        #     })
        except Exception:
            self.data.append({
                "pid": pid,
                "name": "Error",
                "cmdline": "Error"
            })

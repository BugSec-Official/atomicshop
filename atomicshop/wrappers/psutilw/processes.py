import os
import time

import psutil

from ...print_api import print_api
from ..ctyping import file_details_winapi


def kill_process_by_pid(pid: int, print_kwargs: dict = None):
    try:
        print_api(f"Terminating process: {pid}.", **(print_kwargs or {}))
        proc = psutil.Process(pid)
        proc.terminate()  # or proc.kill() if you want to forcefully kill it
        proc.wait(timeout=5)  # Wait up to 5 seconds for the process to terminate
    except psutil.NoSuchProcess:
        # print(f"No process found with PID {pid}.")
        pass
    except psutil.AccessDenied:
        # print(f"Access denied to terminate process with PID {pid}.")
        pass
    except psutil.TimeoutExpired:
        # print(f"Process {pid} did not terminate in time.")
        pass


def get_running_processes_with_exe_info() -> list[dict]:
    """
    Retrieve information about all running processes on the system.
    """
    processes_info: list[dict] = []

    for proc in psutil.process_iter(attrs=["pid", "name", "exe"]):
        try:
            pid = proc.info["pid"]
            name = proc.info["name"]
            exe = proc.info["exe"]

            if exe and os.path.isfile(exe):
                # Get file properties
                file_properties = file_details_winapi.get_file_properties(exe)

                # Add process info to the list
                processes_info.append({
                    "PID": pid,
                    "Name": name,
                    "FilePath": exe,
                    "FileDescription": file_properties["FileDescription"],
                    "FileVersion": file_properties["FileVersion"],
                    "ProductName": file_properties["ProductName"],
                    "ProductVersion": file_properties["ProductVersion"],
                })
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            # Skip processes that cannot be accessed
            continue

    return processes_info

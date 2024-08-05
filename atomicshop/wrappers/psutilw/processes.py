import psutil
import time


def wait_for_process(pid: int):
    """
    Wait for the process with the given PID to finish.
    :param pid: int, PID of the process to wait for.
    :return:
    """
    try:
        # Create a process object for the given PID
        process = psutil.Process(pid)

        # Wait for the process to terminate
        while process.is_running():
            print(f"Process with PID {pid} is still running...")
            time.sleep(1)  # Sleep for 1 second before checking again

        # Refresh process status and get the exit code
        process.wait()
        print(f"Process with PID [{pid}] has finished.")
    except psutil.NoSuchProcess:
        print(f"No process found with PID {pid}")
    except psutil.AccessDenied:
        print(f"Access denied to process with PID {pid}")

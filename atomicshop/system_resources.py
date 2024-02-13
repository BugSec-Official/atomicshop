import os
import shutil
import tempfile
import time
import threading

from .print_api import print_api
from .wrappers.psutilw import cpus, memories, disks


def check_system_resources(
        interval: float = 1,
        get_cpu: bool = True,
        get_memory: bool = True,
        get_disk_io: bool = True,
        get_disk_used_percent: bool = True
):
    """
    Check system resources.
    :param interval: float, interval in seconds.
    :param get_cpu: bool, get CPU usage.
    :param get_memory: bool, get memory usage.
    :param get_disk_io: bool, get TOTAL disk I/O utilization in bytes/s.
    :param get_disk_used_percent: bool, get TOTAL disk used percentage.
    :return:
    """

    threads: list = []
    result: dict = {
        'cpu_usage': None,
        'memory_usage': None,
        'disk_io_write': None,
        'disk_io_read': None,
        'disk_used_percent': None
    }

    def set_cpu_usage():
        result['cpu_usage'] = cpus.get_cpu_usage(interval=interval)

    def set_memory_usage():
        result['memory_usage'] = memories.get_memory_usage()

    def set_disk_io_utilization():
        aggregated_disk_io_utilization = disks.get_disk_io_utilization(interval=interval)['aggregated']
        result['disk_io_read'] = aggregated_disk_io_utilization['read_change_per_sec']
        result['disk_io_write'] = aggregated_disk_io_utilization['write_change_per_sec']

    def set_disk_used_percent():
        result['disk_used_percent'] = disks.get_disk_usage()['total'].percent

    # Create threads for each system resource check.
    if get_cpu:
        threads.append(threading.Thread(target=set_cpu_usage))
    if get_memory:
        threads.append(threading.Thread(target=set_memory_usage))
    if get_disk_io:
        threads.append(threading.Thread(target=set_disk_io_utilization))
    if get_disk_used_percent:
        threads.append(threading.Thread(target=set_disk_used_percent))

    # Start threads.
    for thread in threads:
        thread.start()

    # Wait for all threads to complete.
    for thread in threads:
        thread.join()

    return result


def wait_for_resource_availability(cpu_percent_max: int = 80, memory_percent_max: int = 80, wait_time: float = 5):
    """
    Wait for system resources to be available.
    :param cpu_percent_max: int, maximum CPU percentage. Above that usage, we will wait.
    :param memory_percent_max: int, maximum memory percentage. Above that usage, we will wait.
    :param wait_time: float, time to wait between checks.
    :return: None
    """
    while True:
        cpu, memory, _ = check_system_resources()
        if cpu < cpu_percent_max and memory < memory_percent_max:
            break
        print_api(f"Waiting for resources to be available... CPU: {cpu}%, Memory: {memory}%", color='yellow')
        time.sleep(wait_time)  # Wait for 'wait_time' seconds before checking again


def test_disk_speed(file_size_bytes, file_count, remove_file_after_each_copy: bool = True, target_directory=None):
    """
    Tests disk write and read speeds by generating files in a 'source' directory, copying them to a 'dest' directory
    within the target directory, and optionally removing them after each copy. Now also returns the total execution time.

    :param file_size_bytes: Size of each file in bytes.
    :param file_count: Number of files to generate and copy.
    :param remove_file_after_each_copy: Whether to remove the file after copying to target directory.
    :param target_directory: Directory where files will be copied. Uses a temporary directory if None.
    :return: Tuple of peak write speed, peak read speed, and total execution time in seconds.
    """
    if target_directory is None:
        target_directory = tempfile.mkdtemp()
    else:
        os.makedirs(target_directory, exist_ok=True)

    source_directory = os.path.join(target_directory, 'source')
    dest_directory = os.path.join(target_directory, 'dest')
    os.makedirs(source_directory, exist_ok=True)
    os.makedirs(dest_directory, exist_ok=True)

    write_speeds = []
    read_speeds = []
    created_files = []  # Keep track of all created files for cleanup

    overall_start_time = time.time()  # Start timing the entire operation

    for i in range(file_count):
        # Generate file in source directory
        src_file_path = os.path.join(source_directory, f"tempfile_{i}")
        with open(src_file_path, "wb") as file:
            file.write(os.urandom(file_size_bytes))
        created_files.append(src_file_path)  # Add the file for cleanup

        # Measure write speed
        start_time = time.time()
        shutil.copy(src_file_path, dest_directory)
        end_time = time.time()
        write_speeds.append(file_size_bytes / (end_time - start_time))

        target_file_path = os.path.join(dest_directory, os.path.basename(src_file_path))

        # Measure read speed
        with open(target_file_path, "rb") as file:
            start_time = time.time()
            while file.read(1024 * 1024):  # Read in chunks of 1 MB
                pass
            end_time = time.time()
        read_speeds.append(file_size_bytes / (end_time - start_time))

        if remove_file_after_each_copy:
            os.remove(target_file_path)
            os.remove(src_file_path)

    overall_end_time = time.time()

    # Calculate peak speeds in Bytes/s and total execution time
    peak_write_speed = max(write_speeds)
    peak_read_speed = max(read_speeds)
    total_execution_time = overall_end_time - overall_start_time

    # Cleanup. Remove all created files and directories.
    shutil.rmtree(source_directory)
    shutil.rmtree(dest_directory)

    return peak_write_speed, peak_read_speed, total_execution_time

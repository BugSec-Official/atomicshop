import os
import time
import tempfile
import shutil
import threading

from .print_api import print_api
from .wrappers.psutilw import cpus, memories, disks
from . import system_resource_monitor


def check_system_resources(
        interval: float = 1,
        get_cpu: bool = True,
        get_memory: bool = True,
        get_disk_io_bytes: bool = True,
        get_disk_files_count: bool = True,
        get_disk_busy_time: bool = False,
        get_disk_used_percent: bool = True
):
    """
    Check system resources.
    :param interval: float, interval in seconds.
    :param get_cpu: bool, get CPU usage.
    :param get_memory: bool, get memory usage.
    :param get_disk_io_bytes: bool, get TOTAL disk I/O utilization in bytes/s.
    :param get_disk_files_count: bool, get TOTAL disk files count.
    :param get_disk_busy_time: bool, get TOTAL disk busy time.
        !!! For some reason on Windows it gets the count of files read or written and not the time in ms.
    :param get_disk_used_percent: bool, get TOTAL disk used percentage.
    :return:
    """

    threads: list = []
    result: dict = {
        'cpu_usage': None,
        'memory_usage': None,
        'disk_io_write': None,
        'disk_io_read': None,
        'disk_files_count_read': None,
        'disk_files_count_write': None,
        'disk_busy_time': None,
        'disk_used_percent': None
    }

    def set_cpu_usage():
        result['cpu_usage'] = cpus.get_cpu_usage(interval=interval)

    def set_memory_usage():
        result['memory_usage'] = memories.get_memory_usage()

    def set_disk_io_bytes_change():
        aggregated_disk_io_utilization = (
            disks.get_disk_io(interval=interval, aggregated=True, io_change_bytes=True))['aggregated']
        result['disk_io_read'] = aggregated_disk_io_utilization['read_change_per_sec']
        result['disk_io_write'] = aggregated_disk_io_utilization['write_change_per_sec']

    def set_disk_files_count():
        aggregated_disk_files_count = (
            disks.get_disk_io(interval=interval, aggregated=True, io_file_count=True))['aggregated']
        result['disk_files_count_read'] = aggregated_disk_files_count['read_file_count_per_sec']
        result['disk_files_count_write'] = aggregated_disk_files_count['write_file_count_per_sec']

    def set_disk_busy_time():
        result['disk_busy_time'] = (
            disks.get_disk_io(interval=interval, aggregated=True, io_busy_time=True))['aggregated']['busy_time_percent']

    def set_disk_used_percent():
        result['disk_used_percent'] = disks.get_disk_usage()['aggregated'].percent

    # Create threads for each system resource check.
    if get_cpu:
        threads.append(threading.Thread(target=set_cpu_usage))
    if get_memory:
        threads.append(threading.Thread(target=set_memory_usage))
    if get_disk_io_bytes:
        threads.append(threading.Thread(target=set_disk_io_bytes_change))
    if get_disk_files_count:
        threads.append(threading.Thread(target=set_disk_files_count))
    if get_disk_busy_time:
        threads.append(threading.Thread(target=set_disk_busy_time))
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
        result = check_system_resources(
            get_cpu=True, get_memory=True,
            get_disk_io_bytes=False, get_disk_files_count=False, get_disk_busy_time=False, get_disk_used_percent=False)
        if result['cpu_usage'] < cpu_percent_max and result['memory_usage'] < memory_percent_max:
            break
        print_api(
            f"Waiting for resources to be available... "
            f"CPU: {result['cpu_usage']}%, Memory: {result['memory_usage']}%", color='yellow')
        time.sleep(wait_time)  # Wait for 'wait_time' seconds before checking again


def test_disk_speed_with_monitoring(
        file_settings: list[dict],
        remove_file_after_each_copy: bool = False,
        target_directory=None,
        read_full_file: bool = False,
        monitoring: bool = True,
        print_kwargs: dict = None
):
    """
    Generates files and performs write and read operations in the specified target directory,
    while monitoring disk I/O speeds in a separate thread. Returns the maximum read and write rates,
    and the total operation time.

    :param file_settings: list of dicts, of file settings. Each dict will contain:
        'size': int, size of each file in bytes.
        'count': int, number of files to generate and copy.

        Example:
        file_setting = [
            {'size': 100000000, 'count': 100},
            {'size': 500000000, 'count': 50}
        ]

        This will generate 100 files of 100 MB each, and 50 files of 500 MB each.
    :param remove_file_after_each_copy: Whether to remove the file after copying to target directory.
    :param target_directory: Directory where files will be copied. Uses a temporary directory if None.
    :param read_full_file: Whether to read the full file after copying, or read in chunks.
    :param monitoring: Whether to skip monitoring disk I/O speeds.
    :return: A tuple containing the total operation time in seconds and maximum_io_changes.
    """

    max_io_changes: dict = {}

    if monitoring:
        system_resource_monitor.start_monitoring(
            interval=1, get_cpu=False, get_memory=False, get_disk_io_bytes=True, get_disk_used_percent=False,
            get_disk_files_count=True, calculate_maximum_changed_disk_io=True, use_queue=True)

    if target_directory is None:
        target_directory = tempfile.mkdtemp()
    else:
        os.makedirs(target_directory, exist_ok=True)

    source_directory = os.path.join(target_directory, 'source')
    dest_directory = os.path.join(target_directory, 'dest')
    os.makedirs(source_directory, exist_ok=True)
    os.makedirs(dest_directory, exist_ok=True)

    overall_start_time = time.time()  # Start timing the entire operation

    for file_setting in file_settings:
        for i in range(file_setting['count']):
            # Generate file in source directory
            src_file_path = os.path.join(source_directory, f"tempfile_{i}")
            with open(src_file_path, "wb") as file:
                file.write(os.urandom(file_setting['size']))

            # Measure write speed.
            shutil.copy(src_file_path, dest_directory)

            target_file_path = os.path.join(dest_directory, os.path.basename(src_file_path))
            print_api(f"Copied: {target_file_path}", **(print_kwargs or {}))

            # Measure read speed.
            with open(target_file_path, "rb") as file:
                if read_full_file:
                    file.read()
                else:
                    while file.read(1024 * 1024):  # Read in chunks of 1 MB
                        pass

            if remove_file_after_each_copy:
                os.remove(target_file_path)
                os.remove(src_file_path)

    overall_end_time = time.time()
    total_execution_time = overall_end_time - overall_start_time
    print_api(f"Total execution time: {total_execution_time}", **(print_kwargs or {}))

    # Cleanup. Remove all created files and directories.
    shutil.rmtree(source_directory)
    shutil.rmtree(dest_directory)

    if monitoring:
        # Stop the I/O monitoring.
        max_io_changes = system_resource_monitor.get_result()['maximum_disk_io']
        system_resource_monitor.stop_monitoring()

    return total_execution_time, max_io_changes

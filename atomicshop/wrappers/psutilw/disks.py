import os
import time
import tempfile
import shutil
import threading

import psutil

from ... import system_resources


def get_disk_io_utilization(
        interval: float = 1,
        disk_list: list = None,
        aggregated: bool = True,
        separated: bool = False
) -> dict:
    """
    Get disk utilization based on disk I/O changes, allowing for both aggregated and separated values.
    Windows: because 'psutil.disk_io_counters' before using this function, you may need to execute the following
    command in the command prompt:
        diskperf -y

    :param interval: Sampling interval in seconds to measure I/O changes.
    :param disk_list: List of disks to measure. If None, measure all disks. Affects only when separated is True.
    :param aggregated: Boolean indicating whether to return aggregated utilization.
    :param separated: Boolean indicating whether to return separate utilizations for each disk.
    :return: Disk utilization data.
    """

    io_start_aggregated = None
    io_end_aggregated = None

    io_start_separated = psutil.disk_io_counters(perdisk=True)
    if aggregated:
        io_start_aggregated = psutil.disk_io_counters(perdisk=False)
    time.sleep(interval)
    io_end_separated = psutil.disk_io_counters(perdisk=True)
    if aggregated:
        io_end_aggregated = psutil.disk_io_counters(perdisk=False)

    io_change = {}
    if separated:
        for disk in io_start_separated.keys():
            if disk_list is None or disk in disk_list:
                read_change = io_end_separated[disk].read_bytes - io_start_separated[disk].read_bytes
                write_change = io_end_separated[disk].write_bytes - io_start_separated[disk].write_bytes
                read_change_per_sec = read_change / interval
                write_change_per_sec = write_change / interval
                io_change[disk] = {
                    'read_change_bytes': read_change,
                    'write_change_bytes': write_change,
                    'read_change_per_sec': read_change_per_sec,
                    'write_change_per_sec': write_change_per_sec,
                }

    if aggregated:
        if not io_start_aggregated or not io_end_aggregated:
            raise ValueError('Aggregated disk I/O counters are not available.')
        total_read_change = io_end_aggregated.read_bytes - io_start_aggregated.read_bytes
        total_write_change = io_end_aggregated.write_bytes - io_start_aggregated.write_bytes
        total_read_change_per_sec = total_read_change / interval
        total_write_change_per_sec = total_write_change / interval
        io_change['aggregated'] = {
            'read_change_bytes': total_read_change,
            'write_change_bytes': total_write_change,
            'read_change_per_sec': total_read_change_per_sec,
            'write_change_per_sec': total_write_change_per_sec,
        }

    return io_change


def _get_disk_busy_time(
        interval: float = 1,
        disk_list: list = None,
        aggregated: bool = True,
        separated: bool = False
) -> dict:
    """
    !!! For some reason on Windows it gets the count of files read or written and not the time in ms.

    Get disk busy time, allowing for both aggregated and separated values.
    Windows: because 'psutil.disk_io_counters' before using this function, you may need to execute the following
    command in the command prompt:
        diskperf -y

    :param interval: Sampling interval in seconds to measure I/O changes.
    :param disk_list: List of disks to measure. If None, measure all disks. Affects only when separated is True.
    :param aggregated: Boolean indicating whether to return aggregated utilization.
    :param separated: Boolean indicating whether to return separate utilizations for each disk.
    :return: Disk utilization data.
    """

    io_start_aggregated = None
    io_end_aggregated = None

    io_start_separated = psutil.disk_io_counters(perdisk=True)
    if aggregated:
        io_start_aggregated = psutil.disk_io_counters(perdisk=False)
    time.sleep(interval)
    io_end_separated = psutil.disk_io_counters(perdisk=True)
    if aggregated:
        io_end_aggregated = psutil.disk_io_counters(perdisk=False)

    busy_time = {}
    if separated:
        for disk in io_start_separated.keys():
            if disk_list is None or disk in disk_list:
                read_time = io_end_separated[disk].read_time - io_start_separated[disk].read_time
                write_time = io_end_separated[disk].write_time - io_start_separated[disk].write_time
                read_time_per_sec = read_time / interval
                write_time_per_sec = write_time / interval
                busy_time[disk] = {
                    'read_time_ms': read_time,
                    'write_time_ms': write_time,
                    'read_time_per_sec': read_time_per_sec,
                    'write_time_per_sec': write_time_per_sec,
                    'busy_time': read_time + write_time,
                    'busy_time_per_sec': read_time_per_sec + write_time_per_sec,
                    'busy_time_percent': (read_time + write_time) / interval
                }

    if aggregated:
        if not io_start_aggregated or not io_end_aggregated:
            raise ValueError('Aggregated disk I/O counters are not available.')
        # total_read_time = io_end_aggregated.read_time - io_start_aggregated.read_time
        # total_write_time = io_end_aggregated.write_time - io_start_aggregated.write_time
        total_read_time = io_end_aggregated.read_time
        total_write_time = io_end_aggregated.write_time
        total_read_time_per_sec = total_read_time / interval
        total_write_time_per_sec = total_write_time / interval
        busy_time['aggregated'] = {
            'read_time_ms': total_read_time,
            'write_time_ms': total_write_time,
            'read_time_per_sec': total_read_time_per_sec,
            'write_time_per_sec': total_write_time_per_sec,
            'busy_time': total_read_time + total_write_time,
            'busy_time_per_sec': total_read_time_per_sec + total_write_time_per_sec,
            'busy_time_percent': (total_read_time + total_write_time) / interval
        }

    return busy_time


def get_disk_usage(disk_list: list = None) -> dict:
    """
    Get the usage statistics of disks.

    :param disk_list: List of disks to measure. If None, measure all disks.
    :return:
    """

    disk_usage: dict = {}
    for disk in psutil.disk_partitions():
        if disk_list is None or disk.device in disk_list:
            try:
                disk_usage[disk.device] = psutil.disk_usage(disk.mountpoint)
            except PermissionError as e:
                disk_usage[disk.device] = str(e)

    # Get total disk usage.
    disk_usage['total'] = psutil.disk_usage('/')

    return disk_usage


def test_disk_speed_with_monitoring(
        file_size_bytes: int, file_count: int, remove_file_after_each_copy: bool = False, target_directory=None):
    """
    Generates files and performs write and read operations in the specified target directory,
    while monitoring disk I/O speeds in a separate thread. Returns the maximum read and write rates,
    and the total operation time.

    :param file_size_bytes: Size of each file in bytes.
    :param file_count: Number of files to generate and copy.
    :param remove_file_after_each_copy: Whether to remove the file after copying to target directory.
    :param target_directory: Directory where files will be copied. Uses a temporary directory if None.
    :return: A tuple containing the maximum write speed, maximum read speed, and total operation time in seconds.
    """
    io_speeds = {'write_speed': [], 'read_speed': []}
    stop_thread = False

    def io_monitor():
        """
        Monitors disk I/O speed by checking psutil disk_io_counters every second and calculates the speed.
        This function is intended to run in a separate thread.
        """

        while not stop_thread:
            result = system_resources.check_system_resources(
                interval=1, get_disk_io=True, get_cpu=False, get_memory=False, get_disk_used_percent=False)

            io_speeds['write_speed'].append(result['disk_io_write'])
            io_speeds['read_speed'].append(result['disk_io_read'])

    # Start the I/O monitoring thread
    monitor_thread = threading.Thread(target=io_monitor)
    monitor_thread.start()

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

        shutil.copy(src_file_path, dest_directory)
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

    stop_thread = True
    monitor_thread.join()

    # Determine maximum speeds
    max_write_speed = max(io_speeds['write_speed']) if io_speeds['write_speed'] else 0
    max_read_speed = max(io_speeds['read_speed']) if io_speeds['read_speed'] else 0

    return max_write_speed, max_read_speed, total_operation_time

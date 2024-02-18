import time

import psutil


def get_disk_io(
        interval: float = 1,
        disk_list: list = None,
        aggregated: bool = True,
        separated: bool = False,
        io_change_bytes: bool = False,
        io_file_count: bool = False,
        io_busy_time: bool = False,
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
    :param io_change_bytes: Boolean indicating whether to return I/O change in bytes. Returned dictionary:
        {
            'read_change_bytes': int,
            'write_change_bytes': int,
            'read_change_per_sec': float,
            'write_change_per_sec': float
        }
    :param io_file_count: Boolean indicating whether to return I/O file count. Returned dictionary:
        {
            'read_file_count': int,
            'write_file_count': int,
            'read_file_count_per_sec': float,
            'write_file_count_per_sec': float
        }
    :param io_busy_time: Boolean indicating whether to return I/O busy time.
        !!! For some reason on Windows it gets the count of files read or written and not the time in ms.
        !!! On Ubuntu it gets the time in ms, but for some reason it can return value higher than the interval.
            Which is not possible, so it is not reliable.
        Returned dictionary:
        {
            'read_time_ms': int,
            'write_time_ms': int,
            'read_time_in_sec': float,
            'write_time_in_sec': float,
            'busy_time': int,
            'busy_time_in_sec': float,
            'busy_time_percent': float
        }
    :return: Disk utilization data.
    """

    if not aggregated and not separated:
        raise ValueError('At least one of aggregated or separated must be True.')

    if not io_change_bytes and not io_file_count and not io_busy_time:
        raise ValueError('At least one of io_change_bytes, io_file_count, or io_busy_time must be True.')

    io_start_aggregated = None
    io_end_aggregated = None

    if separated:
        io_start_separated = psutil.disk_io_counters(perdisk=True)
    if aggregated:
        io_start_aggregated = psutil.disk_io_counters(perdisk=False)

    time.sleep(interval)

    if separated:
        io_end_separated = psutil.disk_io_counters(perdisk=True)
    if aggregated:
        io_end_aggregated = psutil.disk_io_counters(perdisk=False)

    io_change = {}
    if separated:
        for disk in io_start_separated.keys():
            if disk_list is None or disk in disk_list:
                io_change[disk] = {}
                if io_change_bytes:
                    read_change = io_end_separated[disk].read_bytes - io_start_separated[disk].read_bytes
                    write_change = io_end_separated[disk].write_bytes - io_start_separated[disk].write_bytes
                    read_change_per_sec = read_change / interval
                    write_change_per_sec = write_change / interval
                    io_change[disk].update({
                        'read_change_bytes': read_change,
                        'write_change_bytes': write_change,
                        'read_change_per_sec': read_change_per_sec,
                        'write_change_per_sec': write_change_per_sec,
                    })
                if io_file_count:
                    read_count = io_end_separated[disk].read_count - io_start_separated[disk].read_count
                    write_count = io_end_separated[disk].write_count - io_start_separated[disk].write_count
                    read_count_per_sec = read_count / interval
                    write_count_per_sec = write_count / interval
                    io_change[disk].update({
                        'read_file_count': read_count,
                        'write_file_count': write_count,
                        'read_file_count_per_sec': read_count_per_sec,
                        'write_file_count_per_sec': write_count_per_sec,
                    })
                if io_busy_time:
                    read_time = io_end_separated[disk].read_time - io_start_separated[disk].read_time
                    write_time = io_end_separated[disk].write_time - io_start_separated[disk].write_time
                    read_time_per_sec = read_time / interval
                    write_time_per_sec = write_time / interval
                    io_change[disk].update({
                        'read_time_ms': read_time,
                        'write_time_ms': write_time,
                        'read_time_per_sec': read_time_per_sec,
                        'write_time_per_sec': write_time_per_sec,
                        'busy_time': read_time + write_time,
                        'busy_time_per_sec': read_time_per_sec + write_time_per_sec,
                        'busy_time_percent': (read_time + write_time) / interval
                    })

    if aggregated:
        if not io_start_aggregated or not io_end_aggregated:
            raise ValueError('Aggregated disk I/O counters are not available.')

        io_change['aggregated'] = {}

        if io_change_bytes:
            aggregated_read_change = io_end_aggregated.read_bytes - io_start_aggregated.read_bytes
            aggregated_write_change = io_end_aggregated.write_bytes - io_start_aggregated.write_bytes
            aggregated_read_change_per_sec = aggregated_read_change / interval
            aggregated_write_change_per_sec = aggregated_write_change / interval
            io_change['aggregated'] = {
                'read_change_bytes': aggregated_read_change,
                'write_change_bytes': aggregated_write_change,
                'total_change_bytes': aggregated_read_change + aggregated_write_change,
                'read_change_per_sec': aggregated_read_change_per_sec,
                'write_change_per_sec': aggregated_write_change_per_sec,
                'total_change_per_sec': aggregated_read_change_per_sec + aggregated_write_change_per_sec
            }
        if io_file_count:
            aggregated_read_count = io_end_aggregated.read_count - io_start_aggregated.read_count
            aggregated_write_count = io_end_aggregated.write_count - io_start_aggregated.write_count
            aggregated_read_count_per_sec = aggregated_read_count / interval
            aggregated_write_count_per_sec = aggregated_write_count / interval
            io_change['aggregated'].update({
                'read_file_count': aggregated_read_count,
                'write_file_count': aggregated_write_count,
                'total_file_count': aggregated_read_count + aggregated_write_count,
                'read_file_count_per_sec': aggregated_read_count_per_sec,
                'write_file_count_per_sec': aggregated_write_count_per_sec,
                'total_file_count_per_sec': aggregated_read_count_per_sec + aggregated_write_count_per_sec
            })
        if io_busy_time:
            aggregated_read_time = io_end_aggregated.read_time - io_start_aggregated.read_time
            aggregated_write_time = io_end_aggregated.write_time - io_start_aggregated.write_time
            aggregated_read_time_per_sec = aggregated_read_time / 1000 / interval
            aggregated_write_time_per_sec = aggregated_write_time / 1000 / interval
            io_change['aggregated'].update({
                'read_time_ms': aggregated_read_time,
                'write_time_ms': aggregated_write_time,
                'read_time_in_sec': aggregated_read_time_per_sec,
                'write_time_in_sec': aggregated_write_time_per_sec,
                'busy_time_ms': aggregated_read_time + aggregated_write_time,
                'busy_time_in_sec': aggregated_read_time_per_sec + aggregated_write_time_per_sec,
                'busy_time_percent': (aggregated_read_time + aggregated_write_time) / 1000 / interval
            })

    return io_change


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
    disk_usage['aggregated'] = psutil.disk_usage('/')

    return disk_usage

import psutil
import time


def get_disk_io_utilization(
        interval: float = 1,
        disk_list: list = None,
        aggregated: bool = True,
        separated: bool = False
) -> dict:
    """
    Get disk utilization based on disk I/O changes, allowing for both aggregated and separated values.

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
                    'write_change_per_sec': write_change_per_sec
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
            'write_change_per_sec': total_write_change_per_sec
        }

    return io_change

from typing import Union
import multiprocessing

from .print_api import print_api
from . import system_resources


def run_check_system_resources(
        interval, get_cpu, get_memory, get_disk_io_bytes, get_disk_files_count, get_disk_used_percent,
        calculate_maximum_changed_disk_io, maximum_disk_io, shared_results, queue=None):
    """
    Continuously update the system resources in the shared results dictionary.
    This function runs in a separate process.
    """

    while True:
        # Get the results of the system resources check function and store them in temporary results dictionary.
        results = system_resources.check_system_resources(
            interval=interval, get_cpu=get_cpu, get_memory=get_memory,
            get_disk_io_bytes=get_disk_io_bytes, get_disk_files_count=get_disk_files_count,
            get_disk_used_percent=get_disk_used_percent)

        if calculate_maximum_changed_disk_io:
            if results['disk_io_read'] > maximum_disk_io['read_bytes_per_sec']:
                maximum_disk_io['read_bytes_per_sec'] = results['disk_io_read']
            if results['disk_io_write'] > maximum_disk_io['write_bytes_per_sec']:
                maximum_disk_io['write_bytes_per_sec'] = results['disk_io_write']
            if results['disk_files_count_read'] > maximum_disk_io['read_files_count_per_sec']:
                maximum_disk_io['read_files_count_per_sec'] = results['disk_files_count_read']
            if results['disk_files_count_write'] > maximum_disk_io['write_files_count_per_sec']:
                maximum_disk_io['write_files_count_per_sec'] = results['disk_files_count_write']
            results['maximum_disk_io'] = maximum_disk_io

        # Update the shared results dictionary with the temporary results dictionary.
        # This is done in separate steps to avoid overwriting the special 'multiprocessing.Manager.dict' object.
        # So we update the shared results dictionary with the temporary results dictionary.
        shared_results.update(results)

        if queue is not None:
            queue.put(results)


class SystemResourceMonitor:
    """
    A class to monitor system resources in a separate process.
    """
    def __init__(
            self,
            interval: float = 1,
            get_cpu: bool = True,
            get_memory: bool = True,
            get_disk_io_bytes: bool = True,
            get_disk_files_count: bool = True,
            get_disk_used_percent: bool = True,
            calculate_maximum_changed_disk_io: bool = False,
            use_queue: bool = False
    ):
        """
        Initialize the system resource monitor.
        :param interval: float, the interval in seconds to check the system resources.
            Default is 1 second.
        :param get_cpu: bool, get the CPU usage.
        :param get_memory: bool, get the memory usage.
        :param get_disk_io_bytes: bool, get the disk I/O utilization of bytes.
        :param get_disk_files_count: bool, get the disk files count in the interval.
        :param get_disk_used_percent: bool, get the disk used percentage.
        :param calculate_maximum_changed_disk_io: bool, calculate the maximum changed disk I/O. This includes the
            maximum changed disk I/O read and write in bytes/s and the maximum changed disk files count.
        :param use_queue: bool, use queue to store results.
            If you need ot get the queue, you can access it through the 'queue' attribute:
            SystemResourceMonitor.queue

            Example:
            system_resource_monitor = SystemResourceMonitor()
            your_queue = system_resource_monitor.queue

            while True:
                if not your_queue.empty():
                    results = your_queue.get()
                    print(results)

        ================

        Usage Example with queue:
        system_resource_monitor = SystemResourceMonitor(use_queue=True)
        system_resource_monitor.start()
        queue = system_resource_monitor.queue
        while True:
            if not queue.empty():
                results = queue.get()
                print(results)

        ================

        Usage Example without queue:
        interval = 1
        system_resource_monitor = SystemResourceMonitor(interval=interval, use_queue=False)
        system_resource_monitor.start()
        while True:
            time.sleep(interval)
            results = system_resource_monitor.get_latest_results()
            print(results)
        """
        # Store parameters as instance attributes
        self.interval: float = interval
        self.get_cpu: bool = get_cpu
        self.get_memory: bool = get_memory
        self.get_disk_io_bytes: bool = get_disk_io_bytes
        self.get_disk_files_count: bool = get_disk_files_count
        self.get_disk_used_percent: bool = get_disk_used_percent
        self.calculate_maximum_changed_disk_io: bool = calculate_maximum_changed_disk_io

        self.manager = multiprocessing.Manager()
        self.shared_results = self.manager.dict()
        self.process = None
        self.maximum_disk_io: dict = {
            'read_bytes_per_sec': 0,
            'write_bytes_per_sec': 0,
            'read_files_count_per_sec': 0,
            'write_files_count_per_sec': 0
        }

        if use_queue:
            self.queue = multiprocessing.Queue()
        else:
            self.queue = None

    def start(self, print_kwargs: dict = None):
        """
        Start the monitoring process.
        :param print_kwargs:
        :return:
        """
        if print_kwargs is None:
            print_kwargs = {}

        if self.process is None or not self.process.is_alive():
            self.process = multiprocessing.Process(target=run_check_system_resources, args=(
                self.interval, self.get_cpu, self.get_memory, self.get_disk_io_bytes, self.get_disk_files_count,
                self.get_disk_used_percent, self.calculate_maximum_changed_disk_io, self.maximum_disk_io,
                self.shared_results, self.queue))
            self.process.start()
        else:
            print_api("Monitoring process is already running.", color='yellow', **print_kwargs)

    def get_latest_results(self) -> dict:
        """
        Retrieve the latest results from the shared results dictionary.
        """
        return dict(self.shared_results)

    def stop(self):
        """
        Stop the monitoring process.
        """
        if self.process is not None:
            self.process.terminate()
            self.process.join()


# === END OF SYSTEM RESOURCE MONITOR. ==================================================================================


SYSTEM_RESOURCES_MONITOR: Union[SystemResourceMonitor, None] = None


def start_monitoring(
        interval: float = 1,
        get_cpu: bool = True,
        get_memory: bool = True,
        get_disk_io_bytes: bool = True,
        get_disk_files_count: bool = True,
        get_disk_used_percent: bool = True,
        calculate_maximum_changed_disk_io: bool = False,
        use_queue: bool = False,
        print_kwargs: dict = None
):
    """
    Start monitoring system resources.
    :param interval: float, interval in seconds.
    :param get_cpu: bool, get CPU usage.
    :param get_memory: bool, get memory usage.
    :param get_disk_io_bytes: bool, get TOTAL disk I/O utilization in bytes/s.
    :param get_disk_files_count: bool, get TOTAL disk files count.
    :param get_disk_used_percent: bool, get TOTAL disk used percentage.
    :param calculate_maximum_changed_disk_io: bool, calculate the maximum changed disk I/O. This includes the
        maximum changed disk I/O read and write in bytes/s and the maximum changed disk files count.
    :param use_queue: bool, use queue to store results.
        Usage Example:
        system_resources.start_monitoring(use_queue=True)
        queue = system_resources.get_monitoring_queue()
        while True:
            if not queue.empty():
                results = queue.get()
                print(results)

    :param print_kwargs: dict, print kwargs.
    :return:
    """

    # if print_kwargs is None:
    #     print_kwargs = {}

    global SYSTEM_RESOURCES_MONITOR

    if not SYSTEM_RESOURCES_MONITOR:
        SYSTEM_RESOURCES_MONITOR = SystemResourceMonitor(
            interval=interval,
            get_cpu=get_cpu,
            get_memory=get_memory,
            get_disk_io_bytes=get_disk_io_bytes,
            get_disk_files_count=get_disk_files_count,
            get_disk_used_percent=get_disk_used_percent,
            calculate_maximum_changed_disk_io=calculate_maximum_changed_disk_io,
            use_queue=use_queue
        )
        SYSTEM_RESOURCES_MONITOR.start()
    else:
        print_api("System resources monitoring is already running.", color='yellow', **(print_kwargs or {}))


def stop_monitoring():
    """
    Stop monitoring system resources.
    :return: None
    """
    global SYSTEM_RESOURCES_MONITOR
    if SYSTEM_RESOURCES_MONITOR is not None:
        SYSTEM_RESOURCES_MONITOR.stop()


def get_monitoring_instance() -> SystemResourceMonitor:
    """
    Get the system resources monitoring instance.
    :return: SystemResourceMonitor
    """
    global SYSTEM_RESOURCES_MONITOR
    return SYSTEM_RESOURCES_MONITOR


def get_result():
    """
    Get system resources monitoring result.

    Usage Example:
    system_resources.start_monitoring()

    while True:
        time.sleep(1)
        result = system_resources.get_result()

        if result:
            print(
                f"{str(result['cpu_usage'])} | {str(result['memory_usage'])} | "
                f"{str(result['disk_io_read'])} | {str(result['disk_io_write'])} | "
                f"{str(result['disk_used_percent'])}"
            )

    :return: dict
    """
    global SYSTEM_RESOURCES_MONITOR
    if SYSTEM_RESOURCES_MONITOR is not None:
        return SYSTEM_RESOURCES_MONITOR.get_latest_results()
    else:
        raise RuntimeError("System resources monitoring is not running.")


def get_result_by_queue():
    """
    Get system resources monitoring result by queue.

    Usage Example:
    system_resources.start_system_resources_monitoring()

    while True:
        result = system_resources.get_result_by_queue()
        print(result)

    :return: dict
    """
    global SYSTEM_RESOURCES_MONITOR
    if SYSTEM_RESOURCES_MONITOR is not None:
        if not SYSTEM_RESOURCES_MONITOR.queue.empty():
            return SYSTEM_RESOURCES_MONITOR.queue.get()
    else:
        raise RuntimeError("System resources monitoring is not running.")


def get_monitoring_queue() -> Union[multiprocessing.Queue, None]:
    """
    Get the monitoring queue.
    :return: multiprocessing.Queue
    """
    global SYSTEM_RESOURCES_MONITOR
    if SYSTEM_RESOURCES_MONITOR is not None:
        return SYSTEM_RESOURCES_MONITOR.queue
    else:
        raise RuntimeError("System resources monitoring is not running.")

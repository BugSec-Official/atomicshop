from typing import Union
import threading
import multiprocessing
import multiprocessing.managers

from .print_api import print_api
from . import system_resources


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
            get_disk_busy_time: bool = False,
            get_disk_used_percent: bool = True,
            calculate_maximum_changed_disk_io: bool = False,
            queue_list: list = None,
            manager_dict = None     # multiprocessing.Manager().dict()
    ):
        """
        Initialize the system resource monitor.
        :param interval: float, the interval in seconds to check the system resources.
            Default is 1 second.
        :param get_cpu: bool, get the CPU usage.
        :param get_memory: bool, get the memory usage.
        :param get_disk_io_bytes: bool, get the disk I/O utilization of bytes.
        :param get_disk_files_count: bool, get the disk files count in the interval.
        :param get_disk_busy_time: bool, get the disk busy time.
            !!! For some reason on Windows it gets the count of files read or written and not the time in ms.
        :param get_disk_used_percent: bool, get the disk used percentage.
        :param calculate_maximum_changed_disk_io: bool, calculate the maximum changed disk I/O. This includes the
            maximum changed disk I/O read and write in bytes/s and the maximum changed disk files count.
        :param queue_list: list, list of queues to store results. The queue type depends on your application.
            If you need to use the results of the System Resource Monitor in another process or several processes
            you can pass several queues in the queue_list to store the results.

            Usage Example with multiprocessing.Manager().dict():
                # Create multiprocessing manager dict that will be shared for monitoring results between the processes.
                manager = multiprocessing.Manager()
                shared_dict = manager.dict()

                # Start the system resource monitor.
                multiprocessing.Process(
                    target=system_resource_monitor.start_monitoring, kwargs={'manager_dict': shared_dict}).start()

            # If you need ot get the queue, you can access it through the 'queue' attribute:
            # SystemResourceMonitor.queue
            #
            # Example:
            # system_resource_monitor = SystemResourceMonitor()
            # your_queue = system_resource_monitor.queue
            #
            # while True:
            #     if not your_queue.empty():
            #         results = your_queue.get()
            #             print(results)
            #
            # ================
            #
            # Usage Example with queue:
            # system_resource_monitor = SystemResourceMonitor(use_queue=True)
            # system_resource_monitor.start()
            # queue = system_resource_monitor.queue
            # while True:
            #     if not queue.empty():
            #         results = queue.get()
            #         print(results)
            #
            # ================
            #
            # Usage Example without queue:
            # interval = 1
            # system_resource_monitor = SystemResourceMonitor(interval=interval, use_queue=False)
            # system_resource_monitor.start()
            # while True:
            #     time.sleep(interval)
            #     results = system_resource_monitor.get_latest_results()
            #     print(results)
        :param manager_dict: multiprocessing.Manager().dict(), a dictionary to store the results.
            If you need to use the results of the System Resource Monitor in another process or several processes
            you can pass the manager_dict to store the results.
        """
        # Store parameters as instance attributes
        self.interval: float = interval
        self.get_cpu: bool = get_cpu
        self.get_memory: bool = get_memory
        self.get_disk_io_bytes: bool = get_disk_io_bytes
        self.get_disk_files_count: bool = get_disk_files_count
        self.get_disk_busy_time: bool = get_disk_busy_time
        self.get_disk_used_percent: bool = get_disk_used_percent
        self.calculate_maximum_changed_disk_io: bool = calculate_maximum_changed_disk_io
        self.queue_list: list = queue_list
        self.manager_dict: multiprocessing.Manager().dict = manager_dict

        self.maximum_disk_io: dict = {
            'read_bytes_per_sec': 0,
            'write_bytes_per_sec': 0,
            'read_files_count_per_sec': 0,
            'write_files_count_per_sec': 0
        }

        # Main thread that gets the monitoring results.
        self.thread: Union[threading.Thread, None] = None
        # Sets the running state of the monitoring process. Needed to stop the monitoring and queue threads.
        self.running: bool = False
        # The shared results dictionary.
        self.results: dict = {}

    def start(self, print_kwargs: dict = None):
        """
        Start the monitoring process.
        :param print_kwargs:
        :return:
        """

        def run_check_system_resources(
                interval, get_cpu, get_memory, get_disk_io_bytes, get_disk_files_count, get_disk_busy_time,
                get_disk_used_percent, calculate_maximum_changed_disk_io, maximum_disk_io, queue_list, manager_dict):
            """
            Continuously update the system resources in the shared results dictionary.
            This function runs in a separate process.
            """

            while self.running:
                # Get the results of the system resources check function and store them in temporary results dictionary.
                results = system_resources.check_system_resources(
                    interval=interval, get_cpu=get_cpu, get_memory=get_memory,
                    get_disk_io_bytes=get_disk_io_bytes, get_disk_files_count=get_disk_files_count,
                    get_disk_busy_time=get_disk_busy_time, get_disk_used_percent=get_disk_used_percent)

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

                if queue_list is not None:
                    for queue in queue_list:
                        queue.put(results)

                # Update the shared results dictionary with the temporary results dictionary.
                # This is done in separate steps to avoid overwriting the special 'multiprocessing.Manager.dict' object.
                # So we update the shared results dictionary with the temporary results dictionary.
                if manager_dict is not None:
                    manager_dict.update(results)

                self.results = results

        if print_kwargs is None:
            print_kwargs = {}

        if self.thread is None:
            self.running = True
            self.thread = threading.Thread(target=run_check_system_resources, args=(
                self.interval, self.get_cpu, self.get_memory, self.get_disk_io_bytes, self.get_disk_files_count,
                self.get_disk_busy_time, self.get_disk_used_percent, self.calculate_maximum_changed_disk_io,
                self.maximum_disk_io, self.queue_list, self.manager_dict))
            self.thread.start()
        else:
            print_api("Monitoring is already running.", color='yellow', **print_kwargs)

    def get_results(self) -> dict:
        """
        Retrieve the latest results.
        """

        return self.results

    def stop(self):
        """
        Stop the monitoring process.
        """
        if self.thread is not None:
            self.running = False
            self.thread.join()


# === END OF SYSTEM RESOURCE MONITOR. ==================================================================================


SYSTEM_RESOURCES_MONITOR: Union[SystemResourceMonitor, None] = None


def start_monitoring(
        interval: float = 1,
        get_cpu: bool = True,
        get_memory: bool = True,
        get_disk_io_bytes: bool = True,
        get_disk_files_count: bool = True,
        get_disk_busy_time: bool = False,
        get_disk_used_percent: bool = True,
        calculate_maximum_changed_disk_io: bool = False,
        queue_list: list = None,
        manager_dict: multiprocessing.managers.DictProxy = None,      # multiprocessing.Manager().dict()
        print_kwargs: dict = None
):
    """
    Start monitoring system resources.
    :param interval: float, interval in seconds.
    :param get_cpu: bool, get CPU usage.
    :param get_memory: bool, get memory usage.
    :param get_disk_io_bytes: bool, get TOTAL disk I/O utilization in bytes/s.
    :param get_disk_files_count: bool, get TOTAL disk files count.
    :param get_disk_busy_time: bool, get TOTAL disk busy time.
        !!! For some reason on Windows it gets the count of files read or written and not the time in ms.
    :param get_disk_used_percent: bool, get TOTAL disk used percentage.
    :param calculate_maximum_changed_disk_io: bool, calculate the maximum changed disk I/O. This includes the
        maximum changed disk I/O read and write in bytes/s and the maximum changed disk files count.
    :param queue_list: list, list of queues to store results. The queue type depends on your application.
        If you need to use the results of the System Resource Monitor in another process or several processes
        you can pass several queues in the queue_list to store the results.
    :param manager_dict: multiprocessing.Manager().dict(), a dictionary to store the results.
        If you need to use the results of the System Resource Monitor in another process or several processes
        you can pass the manager_dict to store the results.

        Usage Example with multiprocessing.Manager().dict():
            # Create multiprocessing manager dict that will be shared for monitoring results between the processes.
            manager = multiprocessing.Manager()
            shared_dict = manager.dict()

            # Start the system resource monitor.
            multiprocessing.Process(
                target=system_resource_monitor.start_monitoring, kwargs={'manager_dict': shared_dict}).start()

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
            get_disk_busy_time=get_disk_busy_time,
            get_disk_used_percent=get_disk_used_percent,
            calculate_maximum_changed_disk_io=calculate_maximum_changed_disk_io,
            queue_list=queue_list,
            manager_dict=manager_dict
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


def get_results():
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
        return SYSTEM_RESOURCES_MONITOR.get_results()
    else:
        raise RuntimeError("System resources monitoring is not running.")

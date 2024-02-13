from typing import Union
import multiprocessing

from .print_api import print_api
from . import system_resources


def run_check_system_resources(
        interval, get_cpu, get_memory, get_disk_io, get_disk_used_percent, shared_results, queue=None):
    """
    Continuously update the system resources in the shared results dictionary.
    This function runs in a separate process.
    """

    while True:
        # Get the results of the system resources check function and store them in temporary results dictionary.
        results = system_resources.check_system_resources(
            interval=interval, get_cpu=get_cpu, get_memory=get_memory,
            get_disk_io=get_disk_io,
            get_disk_used_percent=get_disk_used_percent)
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
            get_disk_io: bool = True,
            get_disk_used_percent: bool = True,
            use_queue: bool = False
    ):
        """
        Initialize the system resource monitor.
        :param interval: float, the interval in seconds to check the system resources.
            Default is 1 second.
        :param get_cpu: bool, get the CPU usage.
        :param get_memory: bool, get the memory usage.
        :param get_disk_io: bool, get the disk I/O utilization.
        :param get_disk_used_percent: bool, get the disk used percentage.
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
        self.interval = interval
        self.get_cpu = get_cpu
        self.get_memory = get_memory
        self.get_disk_io = get_disk_io
        self.get_disk_used_percent = get_disk_used_percent

        self.manager = multiprocessing.Manager()
        self.shared_results = self.manager.dict()
        self.process = None

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
                self.interval, self.get_cpu, self.get_memory, self.get_disk_io,
                self.get_disk_used_percent, self.shared_results))
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


def start_system_resources_monitoring(
        interval: float = 1,
        get_cpu: bool = True,
        get_memory: bool = True,
        get_disk_io: bool = True,
        get_disk_used_percent: bool = True,
        print_kwargs: dict = None
):
    """
    Start monitoring system resources.
    :param interval: float, interval in seconds.
    :param get_cpu: bool, get CPU usage.
    :param get_memory: bool, get memory usage.
    :param get_disk_io: bool, get TOTAL disk I/O utilization in bytes/s.
    :param get_disk_used_percent: bool, get TOTAL disk used percentage.
    :param print_kwargs: dict, print kwargs.
    :return: SystemResourceMonitor
    """

    # if print_kwargs is None:
    #     print_kwargs = {}

    global SYSTEM_RESOURCES_MONITOR

    if not SYSTEM_RESOURCES_MONITOR:
        SYSTEM_RESOURCES_MONITOR = SystemResourceMonitor(
            interval=interval,
            get_cpu=get_cpu,
            get_memory=get_memory,
            get_disk_io=get_disk_io,
            get_disk_used_percent=get_disk_used_percent
        )
        SYSTEM_RESOURCES_MONITOR.start()
    else:
        print_api("System resources monitoring is already running.", color='yellow', **(print_kwargs or {}))


def stop_system_resources_monitoring():
    """
    Stop monitoring system resources.
    :return: None
    """
    global SYSTEM_RESOURCES_MONITOR
    if SYSTEM_RESOURCES_MONITOR is not None:
        SYSTEM_RESOURCES_MONITOR.stop()


def get_system_resources_monitoring_instance() -> SystemResourceMonitor:
    """
    Get the system resources monitoring instance.
    :return: SystemResourceMonitor
    """
    global SYSTEM_RESOURCES_MONITOR
    return SYSTEM_RESOURCES_MONITOR


def get_system_resources_monitoring_result():
    """
    Get system resources monitoring result.

    Usage Example:
    system_resources.start_system_resources_monitoring()

    while True:
        time.sleep(1)
        result = system_resources.get_system_resources_monitoring_result()

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
        return {}

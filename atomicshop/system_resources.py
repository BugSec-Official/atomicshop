import psutil
import time

from .print_api import print_api


def check_system_resources():
    cpu_usage = psutil.cpu_percent(interval=0.1)
    memory_usage = psutil.virtual_memory().percent
    return cpu_usage, memory_usage


def wait_for_resource_availability(cpu_percent_max: int = 80, memory_percent_max: int = 80, wait_time: float = 5):
    """
    Wait for system resources to be available.
    :param cpu_percent_max: int, maximum CPU percentage. Above that usage, we will wait.
    :param memory_percent_max: int, maximum memory percentage. Above that usage, we will wait.
    :param wait_time: float, time to wait between checks.
    :return: None
    """
    while True:
        cpu, memory = check_system_resources()
        if cpu < cpu_percent_max and memory < memory_percent_max:
            break
        print_api(f"Waiting for resources to be available... CPU: {cpu}%, Memory: {memory}%", color='yellow')
        time.sleep(wait_time)  # Wait for 'wait_time' seconds before checking again

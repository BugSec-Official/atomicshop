import psutil


def get_cpu_usage(interval: float = 0.1) -> float:
    """
    Get CPU usage.
    :param interval: Sampling interval in seconds.
    :return: CPU usage.
    """
    return psutil.cpu_percent(interval=interval)

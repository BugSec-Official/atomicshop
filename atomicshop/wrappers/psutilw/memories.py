import psutil


def get_memory_usage():
    """
    Get memory usage in percents.
    :return: float
    """
    return psutil.virtual_memory().percent

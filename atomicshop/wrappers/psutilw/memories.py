import psutil

from ...basics import numbers


def get_memory_usage():
    """
    Get memory usage in percents.
    :return: float
    """
    return psutil.virtual_memory().percent


def get_total_ram(convert_size_to_readable=False) -> tuple[int, str]:
    """
    Get total physical memory in bytes.
    :return:
    """

    memory_size: int = psutil.virtual_memory().total

    if convert_size_to_readable:
        return numbers.convert_bytes_to_readable(memory_size)

    return memory_size, 'B'

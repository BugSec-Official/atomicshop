from typing import Union


def is_divisible(n, k):
    """Return True if n is divisible by k, False otherwise."""

    if n % k == 0:
        return True
    else:
        return False


def find_highest_number(numbers: list[float, int, str]):
    """
    Takes a list of numbers (float or integers) and returns the highest one.

    :param numbers: List of floats or integers.
    :return: The highest number in the list.
    """
    if not numbers:
        raise ValueError('The list of numbers is empty.')

    return max(numbers)


def convert_bytes_to_readable(byte_size: Union[int, float]):
    """
    Convert bytes to a more readable format (KB, MB, GB, etc.) with two numbers after the decimal point.

    :param byte_size: Size in bytes
    :type byte_size: int or float
    :return: A string representing the size in a readable format
    :rtype: str
    """
    # Define the suffixes for each unit of measurement
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    i = 0
    # Convert byte_size to float for division
    byte_size = float(byte_size)

    # Calculate the unit of measurement to use
    while byte_size >= 1024 and i < len(suffixes) - 1:
        byte_size /= 1024.
        i += 1

    # Format the result to include two digits after the decimal point
    readable_format = "{:.2f} {}".format(byte_size, suffixes[i])
    return readable_format

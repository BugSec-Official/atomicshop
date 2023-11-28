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

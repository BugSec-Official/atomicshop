import numpy


def convert_float64_to_int16(data):
    """Converts a numpy array of float64 to int16."""
    return (data * 32767).astype(numpy.int16)


# noinspection PyRedundantParentheses
def concatenate_array_list(array_list: list):
    """
    Concatenates a list of numpy arrays into one numpy array.

    :param array_list: list of numpy arrays.
    :return: numpy array.
    """

    # The expression uses double parentheses, this is not syntax error.
    return numpy.concatenate((array_list))


def is_array_empty(numpy_array: numpy.ndarray):
    """
    Checks if a numpy array is empty.

    :param numpy_array: numpy array.
    :return: boolean.
    """

    if numpy.sum(~numpy_array.any(1)) == len(numpy_array):
        return True
    else:
        return False


def convert_array_to_bytes(numpy_array: numpy.ndarray):
    """
    Converts a numpy array to bytes.

    :param numpy_array: numpy array.
    :return: bytes.
    """

    return numpy_array.tobytes()

def enumerate_from_start_to_end_index(list_instance: list, start_index: int, end_index: int):
    """
    Enumerate a list from start index to end index.

    :param list_instance: list, list to enumerate.
    :param start_index: int, start index.
    :param end_index: int, end index.
    :return: tuple, (index, item).

    Usage example:
    >>> list_to_enumerate = ['a', 'b', 'c', 'd', 'e', 'f', 'g']
    >>> for index, item in enumerate_from_start_to_end_index(list_to_enumerate, 2, 5):
    ...     print(index, item)

    Output:
    2 c
    3 d
    4 e
    5 f
    """

    # This is the fastest approach since we don't slice new list from the old one, like in:
    # for index, item in enumerate(list_instance[start_index:end_index]):
    #     yield index + start_index, item
    # The slice approach is slower because it creates a new list from the old one.
    # The problem is that 'enumerate' function doesn't have 'start_index' and 'end_index' parameter.
    # enumerate()'s 'start' parameter is the index of the first item in the list, but the loop will start from 0 entry
    # in the list, not from the 'start' parameter.

    for i, value in enumerate(list_instance):
        if i < start_index:
            continue
        if i > end_index:
            break
        # print(i, value)
        yield i, value

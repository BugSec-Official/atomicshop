# v1.0.4 - 26.03.2023 - 12:50
def remove_duplicates(list_instance: list):
    # One of the fastest methods.
    seen = set()
    seen_add = seen.add
    return [x for x in list_instance if not (x in seen or seen_add(x))]


def sort_list(list_instance: list) -> None:
    """
    List is an instance. 'sort()' method - sorts the list in place. Meaning you don't have to return anything.

    :param list_instance: list.
    """

    list_instance.sort()


def convert_list_of_strings_to_integers(list_instance: list) -> list:
    return [int(i) for i in list_instance]


def get_difference(list1, list2):
    # This is one of the fastest approaches: https://stackoverflow.com/a/3462202
    s = set(list2)
    return [x for x in list1 if x not in s]

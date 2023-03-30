# v1.0.5 - 28.03.2023 - 17:20
from operator import itemgetter
from json import dumps, loads

from . import dicts


def remove_duplicates(list_of_dicts: list, preserve_order: bool = False):
    # One of the fastest methods.
    # If you want to preserve the Order.
    if preserve_order:
        from collections import OrderedDict
        return OrderedDict((frozenset(item.items()), item) for item in list_of_dicts).values()
    # If the order doesn't matter.
    else:
        return list({frozenset(item.items()): item for item in list_of_dicts}.values())


def sort_by_keys(list_instance: list, key_list: list, case_insensitive: bool = False):
    for key in key_list:
        if case_insensitive:
            list_instance = sorted(list_instance, key=lambda d: d[key].lower())
        else:
            list_instance = sorted(list_instance, key=itemgetter(key))
    return list_instance


def reorder_keys(list_of_dicts: list, key_list: list, inplace: bool = True):
    """
    The function will change the order of keys in a list of dicts.

    :param list_of_dicts: list of dicts.
    :param key_list: list of keys (strings). The order of the keys in the list will be the order of the keys
        in the dicts. After the keys in the 'key_list' are added to the dicts, the remaining keys will be added
        in the order they were in the original dicts.
    :param inplace: bool,
        True: the original list will be modified.
        False: a copy of the original list will be modified.
    """

    if not inplace:
        # Create a copy of the list.
        operate_list = list_of_dicts.copy()
    else:
        # Operate on the original list.
        operate_list = list_of_dicts

    for i, item in enumerate(operate_list):
        operate_list[i] = dicts.reorder_keys(item, key_list)

    return operate_list


def get_difference(main_list: list, check_list: list) -> list:
    """
    The function will return the difference between two lists of dicts.

    :param main_list: list of dicts, the main list that the 'check_list' will be checked against.
    :param check_list: list of dicts, the list that will be checked against the 'main_list'.
    :return: list of dicts, missing items from the 'check_list' that aren't present in the 'main_list'.
    """

    missing_from_main_list = list()
    for item in check_list:
        if item not in main_list:
            missing_from_main_list.append(item)

    return missing_from_main_list


def merge_to_dict(list_of_dicts: list) -> dict:
    """
    The function will merge a list of dicts into one dict.

    :param list_of_dicts: list of dicts.
    :return: dict.
    """

    result_dict = dict()

    for item in list_of_dicts:
        result_dict.update(item)

    return result_dict


def convert_to_set(list_of_dicts, sort_keys: bool = False) -> set:
    """
    The function will convert list of dicts to set.

    :param list_of_dicts: list of dicts.
    :param sort_keys: bool,
        True: the keys will be sorted in the dictionary by AB in ascending order.
    :return: set.
    """

    return set(dumps(x, sort_keys=sort_keys) for x in list_of_dicts)


def convert_from_set(set_object: set) -> list:
    """
    The function will convert set to list of dicts.

    :param set_object: set.
    :return: list of dicts.
    """

    return [loads(x) for x in set_object]

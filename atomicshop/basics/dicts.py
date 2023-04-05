def remove_keys(input_dict: dict, key_list: list) -> None:
    """
    The function will remove a key from dictionary without raising an exception if it doesn't exist.
    Using the 'pop' method, which is one of the fastest.

    Example:
        # Define dictionary.
        test = {
            'key1': '1',
            'key2': '2'
        }

        # Remove 'key2':
        test.pop('key2', None)
        # 'pop' method returns the key value when it is removed if it exists.
        # Result: '2'
        # If the key doesn't exist, then nothing is emitted to console.
        # test.pop('key3', None)
        # If you don't want the method to emit anything to console, assign it to empty variable.
        _ = test.pop('key1', None)

    :param input_dict: dict, that the keys will be removed from.
    :param key_list: list of strings, each entry will contain the name of the key to remove.
    """

    for key in key_list:
        _ = input_dict.pop(key, None)


def reorder_keys(input_dict: dict, key_list: list, skip_keys_not_in_list: bool = False) -> dict:
    """
    The function will change the order of keys in a dictionary.

    :param input_dict: dict, the dictionary that the keys will be reordered.
    :param key_list: list of keys (strings). The order of the keys in the list will be the order of the keys
        in the dicts. After the keys in the 'key_list' are added to the dicts, the remaining keys will be added
        in the order they were in the original dicts.
    :param skip_keys_not_in_list: bool, if True, the keys that aren't in the 'key_list' will be skipped.
        If False, the keys that aren't in the 'key_list' will be added to the end of the new dictionary.
    :return: dict, the new dictionary with the reordered keys.
    """

    new_dict = dict()

    # Iterate through the keys in the 'key_list' and add them to the new dictionary,
    # while removing them from the original.
    # 'pop' method returns the key value when it is removed if it exists.
    for key in key_list:
        new_dict[key] = input_dict.pop(key)

    # If we don't need to skip the keys that aren't in the 'key_list', which is the rest of input dictionary.
    if not skip_keys_not_in_list:
        # Add the remaining keys to the new dictionary.
        new_dict.update(input_dict)

    return new_dict


def convert_key_names(input_dict: dict, key_name_converter: dict) -> dict:
    """
    The function will convert the key names in a dictionary to a new name.

    :param input_dict: dict, the dictionary that the keys will be converted.
    :param key_name_converter: dict, the keys are the current key names and the values are the new key names.
        The keys in the 'key_name_converter' must be the same as the keys in the 'input_dict'.
    :return: dict, the new dictionary with the converted keys.
    """

    new_dict = dict()

    # Iterate through the keys in the 'key_name_converter' and add them to the new dictionary,
    # while removing them from the original.
    # 'pop' method returns the key value when it is removed if it exists.
    for key, new_key in key_name_converter.items():
        new_dict[new_key] = input_dict[key]

    return new_dict


def merge(dict1, dict2) -> dict:
    """
    The function will merge two dictionaries into one.
    If the key exists in both dictionaries, the value from the second dictionary will be used.

    Example:
        # Define dictionaries.
        dict1 = {
            'key1': '1',
            'key2': '2'
        }

        dict2 = {
            'key3': '3',
            'key4': '4'
        }

        # Merge dictionaries.
        merged_dict = {**dict1, **dict2}
        # For Python 3.9 and above:
        merged_dict =  dict1 | dict2
        # Result:
        # {
        #     'key1': '1',
        #     'key2': '2',
        #     'key3': '3',
        #     'key4': '4'
        # }

    :param dict1: dict, the first dictionary to merge.
    :param dict2: dict, the second dictionary to merge.
    :return: dict, the merged dictionary.
    """

    # return {**dict1, **dict2}
    return dict1 | dict2


def find_key_by_value(input_dict, value):
    # This will return set of keys. If non found, will return empty set.
    return {k for k, v in input_dict.items() if v == value}

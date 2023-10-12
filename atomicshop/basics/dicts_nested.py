def merge(dict1: dict, dict2: dict) -> dict:
    merged_dict = dict1

    for key, nested_dict in dict2.items():
        merged_dict[key].update(nested_dict)

    return merged_dict


def find_key_by_value(input_dict: dict, string1: str, string2: str = str(), key_list: list = None):
    """
    Returns list of nested keys that strings of 'value1' and 'value2' were found in the values of 'input_dict'.

    Example:
        urls_dict = {
            'assets': [
                {'url': 'https://test.com/package.zip'},
                {'url': 'https://test2.com/package.zip'}
            ]
        }

    Execution:
        find_key_by_value_in_nested(input_dict=urls_dict, string1='package', string2='.zip')

    Result:
        [['assets', 0, 'url'], ['assets', 1, 'url']]

    :param input_dict: dict, the dictionary that will be searched.
    :param string1: string, that will be checked against values of 'input_dict' with 'contains' operator.
    :param string2: string, that will be checked against values of 'input_dict' with 'contains' operator.
        Both 'string1' and 'string2' are checked with 'and' operator, meaning both strings must be contained against
        the values of the dictionary.
    :param key_list: list. Default is 'None', since it is used for recurse. Meaning, that each time a value
        is a dict or list, it will contain current list iteration, or dictionary key, to build final
        list of keys.
    :return: list of nested keys.
    """

    # Define final list that will be returned, or recurse list of an iteration.
    final_key_list: list = list()

    # If 'key_list' wasn't defined, we'll initialize it. It is needed only for first level of execution.
    # Each recurse level will have some keys.
    if not key_list:
        key_list = list()

    # Iterate through dictionary.
    for key, value in input_dict.items():
        # If value is a dictionary.
        if isinstance(value, dict):
            # Create 'temp_list' of current 'key_list' + the 'key' that we're in.
            temp_list = list(key_list + [key])
            # Pass it to the function again, to search for the strings. If 'string1' and 'string2' were found in that
            # dictionary, get the list of keys it was found in to 'found_list'.
            found_list = find_key_by_value(value, string1, string2, temp_list)
            # If something was found, then add the found list of keys to the 'final_key_list'.
            if found_list:
                final_key_list += found_list
        # Check if 'value' is a list.
        elif isinstance(value, list):
            for i, single_value in enumerate(value):
                temp_list = list(key_list + [key] + [i])
                found_list = find_key_by_value(single_value, string1, string2, temp_list)
                if found_list:
                    final_key_list += found_list
        # For all the other cases.
        else:
            if string1 in str(value) and string2 in str(value):
                temp_list = list(key_list + [key])
                final_key_list.append(temp_list)

    return final_key_list


def find_key_of_last_nest(input_dict: dict) -> list:
    """
    Returns list of keys of the last nest in the dictionary.
    :param input_dict: dict, the dictionary to search.
    :return: list of keys in order.
    """

    for key, value in input_dict.items():
        if isinstance(value, dict):
            return [key] + find_key_of_last_nest(value)
        elif isinstance(value, list):
            return [key] + find_key_of_last_nest(value[0])
        else:
            return [key]


def find_key_of_last_dict(input_dict: dict) -> list:
    """
    Returns list of keys of the last dictionary in the dict.
    :param input_dict: dict, the dictionary to search.
    :return: list of keys in order.
    """

    for key, value in input_dict.items():
        if isinstance(value, dict):
            return [key] + find_key_of_last_dict(value)
        else:
            return []

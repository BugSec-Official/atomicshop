import datetime
from collections.abc import Mapping, Iterable

_PRIMITIVES = (str, int, float, bool, bytes,
               datetime.datetime, datetime.date, datetime.time, type(None))


def get_first_key_name(input_dict: dict) -> str:
    """
    The function will return the first key name in a dictionary.

    :param input_dict: dict, the dictionary to get the first key name.
    :return: str, the first key name in the dictionary.
    """

    return next(iter(input_dict))


def get_first_key_and_value_dict(input_dict: dict) -> dict:
    """
    The function will return the first key and value in a dictionary.

    :param input_dict: dict, the dictionary to get the first key and value.
    :return: dict, the first key and value in the dictionary.
    """

    first_key = get_first_key_name(input_dict)
    return {first_key: input_dict[first_key]}


def get_last_added_key_value(input_dict: dict) -> dict:
    """
    The function will return the last added key and value in a dictionary.

    :param input_dict: dict, the dictionary to get the last added key and value.
    :return: dict, the last added key and value in the dictionary.
    """

    last_key = list(input_dict.keys())[-1]
    return {last_key: input_dict[last_key]}


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


def sort_by_values(input_dict: dict, reverse: bool = False) -> dict:
    """
    The function will sort a dictionary by its values.
    Example:
        # Define dictionary.
        test = {
            'key1': '1',
            'key2': '2',
            'key3': '8',
            'key4': '37',
            'key5': '5',
            'key6': '23'
        }

        # Sort dictionary.
        sorted_dict = sort_by_values(test, reverse=True)

        # Result:
        # {
        #     'key4': '37',
        #     'key6': '23',
        #     'key3': '8',
        #     'key5': '5',
        #     'key2': '2',
        #     'key1': '1'
        # }

    :param input_dict: dict, the dictionary to sort.
    :param reverse: bool, if True, the dictionary will be sorted in reverse order.
    :return: dict, the sorted dictionary.
    """

    return dict(sorted(input_dict.items(), key=lambda item: item[1], reverse=reverse))


def convert_object_with_attributes_to_dict(
        obj,
        include_private_1: bool = False,
        include_private_2: bool = False,
        skip_attributes: list = None,
        recursion_level: int = 0
) -> dict:
    """
    The function will convert an object with attributes to a dictionary. Each attribute will be a key in the dictionary
    and the value will be the attribute value.
    :param obj: object, the object to convert.
    :param include_private_1: bool, if True, the private attributes that start with one underscore will be included.
    :param include_private_2: bool, if True, the private attributes that start with two underscores will be included.
    :param skip_attributes: list of strings, each entry will contain the name of the attribute to skip.
    :param recursion_level: int, the current recursion level. Used to prevent infinite recursion.
    :return:
    """

    if skip_attributes is None:
        skip_attributes = []

    skip_set = set(skip_attributes)

    def should_include(attr_name: str) -> bool:
        if attr_name in skip_set:
            return False
        if attr_name.startswith("_") and not attr_name.startswith("__"):
            return include_private_1
        if attr_name.startswith("__"):
            return include_private_2
        return True

    def convert_value(value, level: int):
        # Base cases
        if level <= 0 or isinstance(value, _PRIMITIVES):
            return value

        # Mapping (dict): recurse into values (dict is iterable over keys, so special-case it)
        if isinstance(value, Mapping):
            return {k: convert_value(v, level - 1) for k, v in value.items()}

        # Common container types: preserve container type
        if isinstance(value, list):
            return [convert_value(item, level - 1) for item in value]
        if isinstance(value, tuple):
            return tuple(convert_value(item, level - 1) for item in value)
        if isinstance(value, set):
            return {convert_value(item, level - 1) for item in value}
        if isinstance(value, frozenset):
            return frozenset(convert_value(item, level - 1) for item in value)

        # Recurse into attribute-bearing objects only (avoid `isinstance(x, object)` which is always True)
        if hasattr(value, "__dict__") or hasattr(value, "__slots__"):
            return convert_object_with_attributes_to_dict(
                value,
                include_private_1=include_private_1,
                include_private_2=include_private_2,
                skip_attributes=skip_attributes,
                recursion_level=level - 1
            )

        # Fallback: return as-is (e.g., iterators/generators/custom types you don't want to consume)
        return value

    obj_dict = {}

    # Your original behavior: iterate attribute names via dir()
    for attr_name in dir(obj):
        if not should_include(attr_name):
            continue

        # Filter out callable attributes (methods, etc.). We only want attributes.
        try:
            if callable(getattr(obj, attr_name)):
                continue
        except AttributeError:
            # Some descriptors/properties may raise; skip them
            continue

        try:
            attr_value = getattr(obj, attr_name)
        except AttributeError:
            continue

        if recursion_level > 0:
            attr_value = convert_value(attr_value, recursion_level)

        obj_dict[attr_name] = attr_value

    return obj_dict


def convert_complex_object_to_dict(data):
    """ Function that converts complex objects to dict recursively """

    # 1. Extracts only the first level of objects. No byte decoding.
    # new_dict = dict()
    # for key, value in vars(obj).items():
    #     new_dict.update({key: str(value)})
    # return new_dict

    # 2. Extracts only the first level of objects. Tries to decode bytes, if exception rises stores string as is.
    # new_dict = dict()
    # for key, value in vars(obj).items():
    #     try:
    #         new_dict.update({key: value.decode('utf-8')})
    #     except Exception:
    #         new_dict.update({key: str(value)})
    # return new_dict

    # 3. Decompress all the objects, save objects as is (no byte decoding).
    if hasattr(data, "__dict__"):
        # 'vars' return a dictionary of all the variables in a class / object.
        # 'map' iterates through function 'dict_converter' all the values of the second argument and returns a list
        # of all iterations of the function result.
        function_return = dict(map(convert_complex_object_to_dict, vars(data).items()))
        # If 'data' type is 'bytes'
    elif isinstance(data, dict):
        function_return = dict(map(convert_complex_object_to_dict, data.items()))
    elif isinstance(data, tuple):
        function_return = tuple(map(convert_complex_object_to_dict, data))
    elif isinstance(data, list):
        function_return = list(map(convert_complex_object_to_dict, data))
    # One value objects.
    elif isinstance(data, datetime.datetime):
        function_return = data.strftime('%Y-%m-%d-%H:%M:%S')
    elif isinstance(data, bytes) or isinstance(data, bytearray):
        function_return = str(data)

        # Don't want to use the next method, since there will be different formatted strings / messages. And we don't
        # want that, since we can't manipulate it easily later.
        # # Try to decode, if fails, return string.
        # try:
        #     function_return = data.decode(encoding='utf-8')
        # except Exception:
        #     function_return = str(data)
        #     pass
    # Any other type will return as is (something that 'dict()' function can handle), like strings and integers.
    else:
        function_return = data

    return function_return


def convert_tuples_to_lists(obj):
    """
    Convert all tuples in object to lists. The first  input 'obj' can be a dictionary, list or tuple.
    :param obj: dict, list, tuple, the object to convert.
    :return:
    """
    if isinstance(obj, dict):
        return {k: convert_tuples_to_lists(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_tuples_to_lists(element) for element in obj]
    elif isinstance(obj, tuple):
        return list(obj)
    return obj


def convert_int_to_str_in_mixed_lists(item):
    """
    Recursively traverse an item (which can be a dictionary, list, tuple, or a basic data type).
    If a list or a tuple contains both integers and strings, convert all integers to strings.
    This is useful when converting indexing a dictionary with mixed lists into Elasticsearch.
    Since Elasticsearch doesn't support mixed lists, we need to convert integers to strings.
    """

    if isinstance(item, dict):
        # If the item is a dictionary, apply the function to each value.
        return {key: convert_int_to_str_in_mixed_lists(value) for key, value in item.items()}
    elif isinstance(item, (list, tuple)):
        # If the item is a list or a tuple, check if it contains both integers and strings.
        contains_int = any(isinstance(elem, int) for elem in item)
        contains_str = any(isinstance(elem, str) for elem in item)

        if contains_int and contains_str:
            # If both integers and strings are present, convert integers to strings.
            return type(item)(str(elem) if isinstance(elem, int) else elem for elem in item)
        else:
            # Otherwise, apply the function to each element.
            return type(item)(convert_int_to_str_in_mixed_lists(elem) for elem in item)
    else:
        # If the item is neither a dictionary, list, nor tuple, return it as is.
        return item


def convert_dict_to_list_of_key_value_pairs(input_dict: dict) -> list:
    """
    Convert a dictionary to a list of key-value dicts.
    :param input_dict: dict, the dictionary to convert.
    :return: list, the list of key-value pairs.
    """
    return [{key: value} for key, value in input_dict.items()]

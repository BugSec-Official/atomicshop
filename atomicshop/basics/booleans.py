def is_only_1_true_in_list(
        booleans_list_of_tuples: list[tuple],
        raise_if_all_false: bool = True
) -> None:
    """
    Check if only one boolean can be 'True' from a list of booleans
    :param booleans_list_of_tuples: list of tuples, Structure:
        [(value, string name of the setting you want to print to the user to be aware of), ...]
    :param raise_if_all_false: bool, If True, exception will be raised if all booleans are False.
    :return: None
    """

    # Filter to get all the `True` conditions and their associated names
    true_conditions = [name for value, name in booleans_list_of_tuples if value]

    # Count the number of True values
    true_count = len(true_conditions)

    if true_count == 1:
        # Only one value is True, which is acceptable
        # print(f"Only one condition is True: {true_conditions[0]}.")
        pass
    elif true_count > 1:
        # More than one value is True, raise an exception
        raise ValueError(f"Multiple conditions are True: {', '.join(true_conditions)}.")
    elif true_count == 0 and raise_if_all_false:
        # None of the values are True, and the user does not want to ignore this case
        raise ValueError("No conditions are True, and raise_if_all_false is set to True.")
    else:
        # If no True values and no_raise_if_all_false is True, just pass silently
        # print("No conditions are True (but raise_if_all_false is set to False).")
        pass


def convert_string_to_bool(string: str) -> bool:
    if string.lower() == 'true':
        return True
    elif string.lower() == 'false':
        return False
    else:
        raise ValueError(f"The value '{string}' is not a boolean.")

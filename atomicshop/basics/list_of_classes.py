from operator import attrgetter


def sort_by_attributes(
        list_instance: list,
        attribute_list: list,
        reverse: bool = False,
        case_insensitive: bool = False
):
    """
    Sort a list of objects by their attributes.

    :param list_instance: list of objects.
    :param attribute_list: list of attributes (strings). The sorting will be done by the attributes in the list.
        In the appearing order in the list.
    :param reverse: bool, sort in reverse order.
    :param case_insensitive: bool, sorting will be case-insensitive.
    """

    for attribute in attribute_list:
        if case_insensitive:
            list_instance = sorted(
                list_instance, key=lambda obj: getattr(obj, attribute).lower(), reverse=reverse
            )
        else:
            list_instance = sorted(
                list_instance, key=attrgetter(attribute), reverse=reverse
            )
    return list_instance

import types


def isinstance_checks(object_to_check):
    if isinstance(object_to_check, frozenset):
        return 'frozenset'
    elif isinstance(object_to_check, set):
        return 'set'
    elif isinstance(object_to_check, list):
        return 'list'
    elif isinstance(object_to_check, types.GeneratorType):
        return 'generator'
    elif isinstance(object_to_check, dict):
        return 'dict'
    elif isinstance(object_to_check, tuple):
        return 'tuple'
    elif isinstance(object_to_check, str):
        return 'str'
    elif isinstance(object_to_check, int):
        return 'int'
    elif isinstance(object_to_check, float):
        return 'float'
    elif isinstance(object_to_check, bool):
        return 'bool'
    elif isinstance(object_to_check, type(None)):
        return 'None'
    else:
        return 'unknown'

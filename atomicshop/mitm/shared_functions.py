# v1.0.2 - 21.03.2023 13:50
import json
# Needed to convert datetime objects inside 'dict_converter' function.
import datetime
# Needed to get the function caller module.
import inspect

from ..logger_custom import CustomLogger


# If the string has several dot characters (".") - return the most right string after the last dot.
# Meaning if the class name contains several child classes like: classes.parsers.parser_something,
# Return only the name of the parser itself: parser_something
# Building the module names for each class.
def build_module_names(class_name: str):
    # The "function_class_name" variable is split by ".rpartition('.')" method, which returns a tuple of 3 strings.
    # 1st string is everything before the last splitting character (the dot "."), 2nd is the splitting character itself
    # and 3rd is the right part after the last splitting character. So, we're using the "[2]" to choose the third part
    # of that tuple.
    left_string_part, current_delimiter, module_name = class_name.rpartition('.')
    engine_name = left_string_part.rpartition('.')[2]

    logger_name = engine_name + "." + module_name

    return logger_name, engine_name, module_name


def create_custom_logger():
    """ Function returns CustomLogger instance of class name '__name__' """

    # Get the current stack frame record.
    current_frame = inspect.currentframe()
    # Get the calling stack frame record. First 'f_back' is the calling class name.
    calling_frame = current_frame.f_back
    # 'f_globals' is a dictionary of all the global variables of the calling initiated class.
    class_name = calling_frame.f_globals['__name__']
    # Get the logger name only.
    logger_name = build_module_names(class_name)[0]

    return CustomLogger(logger_name)


def dict_converter(data):
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
        function_return = dict(map(dict_converter, vars(data).items()))
        # If 'data' type is 'bytes'
    elif isinstance(data, dict):
        function_return = dict(map(dict_converter, data.items()))
    elif isinstance(data, tuple):
        function_return = tuple(map(dict_converter, data))
    elif isinstance(data, list):
        function_return = list(map(dict_converter, data))
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


def get_json(obj):
    """ Convert any nested object to json / dict and values to string as is """

    return json.dumps(obj, default=dict_converter)

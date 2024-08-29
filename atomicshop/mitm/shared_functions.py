import json
import inspect

from ..wrappers.loggingw import loggingw
from ..basics import dicts

from . import config_static


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
    engine_logger_part = build_module_names(class_name)[0]
    logger_name = f'{config_static.MainConfig.LOGGER_NAME}.{engine_logger_part}'

    return loggingw.get_logger_with_level(logger_name)


def get_json(obj):
    """ Convert any nested object to json / dict and values to string as is """

    return json.dumps(obj, default=dicts.convert_complex_object_to_dict)

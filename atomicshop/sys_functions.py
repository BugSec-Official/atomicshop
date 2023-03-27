# v1.0.0 - 21.03.2023 18:00
import sys


def sys_insert_custom_modules_path(modules_directory: str):
    """
    Function adds 'modules_directory' to 'sys.path', which should contain the 'modules' directory.

    Example for modules directory that you import your classes:
        from modules.some_class import SomeClass
    The module is in the path:
        d:\\SomeDirectory\\modules\\some_class.py
    So, we need to add the directory to 'sys.path':
        d:\\SomeDirectory
    The function usage will be:
        sys_insert_custom_modules_path('d:\\SomeDirectory')

    :param modules_directory:
    :return:
    """

    # Add the path to known paths at second place (sys.path[1]) and not the first (sys.path[0]), since it is reserved.
    # Better not to use 'sys.path.append' because it will set the directory to the last place.
    sys.path.insert(1, modules_directory)

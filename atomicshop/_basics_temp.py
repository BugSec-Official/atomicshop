# v1.0.0
# THIS FILE IS TEMPORARY.
import os
import sys
import inspect


def get_frame_arguments(inspect_frame):
    return inspect.getargvalues(inspect_frame)


def get_current_frame():
    return inspect.currentframe().f_back


def add_back_frame(frame):
    return getattr(frame, 'f_back')


def add_number_of_back_frames(frame, back_level: int = 1):
    for i in range(back_level):
        frame = add_back_frame(frame)

    return frame


def get_variable_in_caller_frame(frame, variable_string: str):
    while True:
        frame_arguments = get_frame_arguments(frame)
        if variable_string in frame_arguments.locals:
            return frame_arguments.locals[variable_string]
        else:
            frame = add_back_frame(frame)


def get_script_directory():
    """
    The function gets '__file__' variable from the caller function, since the caller function should be the main script
    it will give us full file path to that script. Then we'll extract only the working directory of that script,
    and return it.

    :return: string of full path to working script directory.
    """

    # Get current live frame.
    frame = get_current_frame()
    # We'll add one back frame to the current frame, since current frame can't be the caller anyway.
    frame = add_number_of_back_frames(frame)
    # The only frame that can have the '__file__' variable is the one that did the first call. Meaning if the call
    # to function 'test()' that resides in file 'functions.py', was made from 'main.py', the first '__file__' variable
    # will appear only in the 'main.py' and in the 'functions.py', since 'functions.py' wasn't the one that did
    # the first call. 'get_variable_in_caller_frame' will go up in frames until it will find the '__file__' variable,
    # and it will be 100% the main script, file, since it was the one that did the first call.
    file_path: str = get_variable_in_caller_frame(frame, '__file__')
    # Get 'file_path's working directory.
    script_directory: str = get_script_directory_from_file_path(file_path)

    return script_directory


def get_script_directory_from_file_path(file_path: str):
    """
    Function will extract the working directory of the full file path from input.

    :param file_path: string with full file path.
    :return: string of working directory of that file.
    """
    return os.path.dirname(os.path.abspath(file_path))


def cut_last_directory(directory_path: str):
    """
    Function will cut the last directory and return a string without it.

    :param directory_path: string of full path to directory to cut.
    :return: string of full path without last directory.
    """
    return directory_path.rsplit(os.sep, maxsplit=1)[0]


def sys_insert_custom_modules_path(modules_directory: str):
    # noinspection GrazieInspection
    """
    Function adds 'modules_directory' to 'sys.path', which should contain the 'modules' directory.

    Example for modules directory that you import your classes:
        from modules.test import SomeClass
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

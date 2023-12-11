import os
import ast
import importlib
from pathlib import Path

from ..file_io.file_io import read_file


def create_empty_class():
    """
    Function creates empty class, you can add parameters to it dynamically.
    Example:
        dynamic_class = create_empty_class()
        dynamic_class.parameter1 = 'test1'
        dynamic_class.parameter2 = 'test2'

    You can create class only and initiate it later:
        dynamic_class = type('', (), {})
        dynamic_class()

    :return: class instance.
    """

    dynamic_class = type('', (), {})()
    return dynamic_class


def get_module_name_from_file_path(file_directory_path: str, file_path: str) -> str:
    """
    Function that extracts module name string from file path.

    Example:
        C:\\Project1\\modules\\classes\\filesystem.py
    The main script that is calling the module resides in:
        C:\\Project1\\main_script.py
    To load the module, it needs to be specified as:
        import modules.classes.filesystem
    This function gets as input the script directory (C:\\Project1), extracts it from the 'file_path' and gets rid
    of the file extension.

    Usage:
        get_module_name_from_file_path('C:\\Project1', 'C:\\Project1\\modules\\classes\\filesystem.py')
    Returns:
        'modules.classes.filesystem'

    :param file_directory_path: string, of file full path to working directory of the main script that need
        to call the import.
    :param file_path: string, of full file path to the module that needs ot be imported.
    :return: string, of module name.
    """

    # Removing suffix.
    file_path_no_suffix = Path(file_path).stem
    # Removing the script directory.
    path_without_script_directory = file_path_no_suffix.replace(file_directory_path + os.sep, '')
    # Changing slashes to dots.
    module_name_string = path_without_script_directory.replace(os.sep, '.')

    return module_name_string


def get_class_names_from_file(file_path: str, **kwargs) -> list:
    """
    Function to extract all class names from external file modules in the filesystem.

    :param file_path: string, of full file path to python file module.
    :return: list of class names inside the module.
    """

    # Read the string contents of the module file.
    file_contents: str = read_file(file_path=file_path, file_mode='r', **kwargs)

    # Parsing the string contents by ast module.
    ast_parse = ast.parse(file_contents)
    # Extracting all the class names from the parsed content.
    classes_name_list = [node.name for node in ast.walk(ast_parse) if isinstance(node, ast.ClassDef)]

    return classes_name_list


def import_module_by_string(module_name_string: str) -> object:
    """
    # Creating class objects from strings. To initialize class instance we call it as usual. Example: "ClientMessage()"
    # This is the best way to import classes dynamically:
    # https://docs.python.org/3/library/importlib.html#importlib.__import__
    # Giving objects the same name as the classes in the files.

    :param module_name_string: module name string (modules.engine.first)
    :return: returns imported module callable.
    """

    # Importing the object.
    imported_module_callable = importlib.import_module(module_name_string)
    # Assigning the class instance to a variable, "class_string" is the name of the class itself inside the file
    # function_class_instance = getattr(imported_module, class_string)

    # "importlib" has also another method of importing directly from file path + file name:
    # https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
    # Took example from:
    # https://stackoverflow.com/questions/67631/how-to-import-a-module-given-the-full-path?page=1&tab=votes#tab-top
    # import importlib.util
    # function_spec = importlib.util.spec_from_file_location(function_filename_no_suffix, function_directory)
    # function_module = importlib.util.module_from_spec(function_spec)
    # StackOverflow example omitted this: sys.modules[function_filename_no_suffix] = function_module
    # function_spec.loader.exec_module(function_module)
    # function_module.MyClass()
    # or try
    # class_string = "MyClass"
    # function_class_instance = getattr(module, class_string)
    # The only problem with this method is if you're using shared modules in your classes that you import, example:
    # from ..shared_functions import test_function
    # This indicates that "shared_functions" in directory above of the current module. Which is relative, and
    # you will get an error "ImportError: attempted relative import with no known parent package"
    # Since it should be in the same directory.

    return imported_module_callable


def add_class_name_to_imported_module(imported_module, class_name: str):
    """
    Function uses already imported module object:
        imported_module = importlib.import_module(module_name_string)
    and adds to it the class name that we want to execute.

    Example file:
        C:\\Project1\\modules\\classes\\filesystem.py
    Contents:
        class GetFileSystem:

    If we already know the name of the class and its file path then normally we would import as:
        from modules.classes.filesystem import GetFileSystem
    and to initialize it, we would run:
        GetFileSystem()
    If we don't know the placement of the file and also the name of the class name, we would use the os path
    modules in order to find file and extract all the class names.
    So:
        imported_module = importlib.import_module(modules.classes.filesystem)
    And to execute the class name we would need to add it as attribute to already imported module.
        imported_class = getattr(imported_module, 'GetFileSystem')
    Initialize regularly:
        imported_class()

    ----------------------------------------------
    Function usage:
        # Call the function.
        imported_class = add_class_name_to_imported_module(imported_module, class_name_string)
        # Initialize module:
        imported_class()

    :param imported_module: result of the function 'importlib.import_module'
    :param class_name: string of the class name that resides inside module.
    :return: imported class.
    """

    return getattr(imported_module, class_name)


def import_first_class_name_from_module_name(module_name: str, **kwargs):
    # Import the module.
    imported_module = import_module_by_string(module_name)
    # Get the first class name from the module python file. Pass only custom api arguments.
    class_name: str = get_class_names_from_file(imported_module.__file__, **kwargs)[0]
    # Add class name attribute to the imported module.
    imported_class = add_class_name_to_imported_module(imported_module, class_name)

    return imported_class


def import_first_class_name_from_file_path(script_directory: str, file_path: str, **kwargs):
    # Get the module name string.
    module_name: str = get_module_name_from_file_path(script_directory, file_path)

    # Import first class from the module.
    imported_class = import_first_class_name_from_module_name(module_name, **kwargs)

    return imported_class


def get_attributes(
        obj,
        include_private_1: bool = False,
        include_private_2: bool = False
) -> list[str]:
    """
    Function returns all attributes of the object.
    :param obj: object, the object to get attributes from.
    :param include_private_1: bool, if True, the private attributes that start with one underscore will be included.
    :param include_private_2: bool, if True, the private attributes that start with two underscores will be included.
    :return: list, of attributes.
    """

    attributes = []
    # Get all attributes of obj
    for attr_name in dir(obj):
        # Check for private attributes with one underscore.
        if attr_name.startswith("_") and not attr_name.startswith("__"):
            if not include_private_1:
                continue
        # Check for private attributes with two underscores (dunder methods).
        elif attr_name.startswith("__"):
            if not include_private_2:
                continue

        attributes.append(attr_name)

    return attributes

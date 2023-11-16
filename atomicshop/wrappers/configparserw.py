import os
import configparser
from typing import Any

from ..print_api import print_api
from ..basics import lists
from .. import filesystem


class ConfigParserWrapper:
    """
    ImportConfig class is responsible for importing 'config.ini' file and its variables.
    """

    def __init__(self, file_name: str = 'config.ini', directory_path: str = None, file_path: str = None):
        """
        The function will initialize the 'ImportConfig' object.
        You can specify either full 'file_path' or 'directory_path' and 'file_name'.
        You can specify only 'directory_path' and 'config.ini' will be used as default file name.

        :param file_name: The name of the file to be imported. Default is 'config.ini'.
        :param directory_path: The directory that 'config.ini' file is in.
        :param file_path: sting, the full path to the file.
        """

        if not directory_path and not file_path:
            raise ValueError("You must specify either 'directory_path' or 'file_path'.")
        elif directory_path and file_path:
            raise ValueError("You can't specify both 'directory_path' and 'file_path'.")

        self.file_name: str = file_name
        self.directory_path: str = directory_path
        self.file_path: str = file_path

        self.config_parser = None
        # Final configuration dictionary.
        self.config = dict()

        if file_path:
            self.file_path: str = file_path
        else:
            self.file_path: str = self.directory_path + os.sep + self.file_name

        # After that you can use 'convert_string_values' function to convert certain key values to other types.

    def read_to_dict(self, unicode_encoding: bool = False) -> dict[Any, Any]:
        """
        Usage Example:
            # If 'config.ini' in current working directory of the script.
            working_directory = os.path.dirname(os.path.abspath(__file__))
            # Open config.ini
            config = ImportConfig(directory_path=working_directory)
            config.read_to_dict()

        :param unicode_encoding: boolean, that sets if 'configparser.ConfigParser()' should use 'unicode' encoding.
        :return: parsed dict.
        """

        # Reading "config.ini".
        if not self.config_parser:
            self.initialize_config_parser()
        self.read_config_file(unicode_encoding=unicode_encoding)
        self.convert_config_to_dict()
        return self.config

    def write_to_file(self, config_dict: dict = None, file_path: str = None, **kwargs):
        """
        The function will write the 'config_dict' to file.
        :param config_dict: dictionary to write to file.
            If specified, the configparser object will import the 'config_dict' and write to file.
            If not specified, the existing configparser object will be written to file.
        :param file_path: string, full path to file. If 'file_path' is not specified, the 'file_path' of the object
            will be used.
        :param kwargs:
        :return:
        """

        if not file_path:
            file_path = self.file_path

        if config_dict:
            self.update_config(config_dict=config_dict, overwrite_all=True, **kwargs)

        # Writing to file.
        with open(file_path, 'w') as config_file:
            self.config_parser.write(config_file)

    def update_config(
            self,
            config_dict: dict,
            overwrite_all: bool = False,
            overwrite_section_only: bool = False
    ):
        """
        The function will update the 'config_dict' to the existing 'config' dict.
        :param config_dict: dictionary to update to the existing 'config' dict and ConfigParser object.
        :param overwrite_all: boolean, that sets if the existing 'config' dict and ConfigParser will be overwritten.
            If 'True' the existing 'config' dict and ConfigParser will be overwritten.
        :param overwrite_section_only: boolean, that sets if the specific 'config' dict and ConfigParser section
            will be overwritten, but not the whole configuration.
        :return:
        """

        if overwrite_all and overwrite_section_only:
            raise ValueError("You can't specify both 'overwrite_all' and 'overwrite_section_only'.")

        if not self.config_parser or overwrite_all:
            self.initialize_config_parser()

        if overwrite_all:
            self.config = config_dict

            # Add sections and values from the dictionary
            for section, section_dict in self.config.items():
                # self.config_parser.add_section(section)
                for key, value in section_dict.items():
                    self.config_parser.set(section, key, value)
        elif overwrite_section_only:
            # Setting the 'config' dict to 'configparser' object.
            for section, section_dict in config_dict.items():
                if self.config and section not in self.config:
                    self.config[section] = section_dict

                for key, value in section_dict.items():
                    self.config_parser.set(section, key, value)
        else:
            # Updating the 'configparser' object and 'config' dict if exists.
            for section, section_dict in config_dict.items():
                if self.config:
                    if section not in self.config:
                        self.config[section] = section_dict
                    else:
                        self.config[section].update(section_dict)

                if section not in self.config_parser:
                    self.config_parser[section] = section_dict
                else:
                    self.config_parser[section].update(section_dict)

    def read_file_overwrite_with_update(
            self,
            config_dict: dict,
            overwrite_all: bool = False,
            overwrite_section_only: bool = False
    ):
        """
        The function will read the file and update the 'config' dict and 'configparser' object and overwrite the
        config file.
        :param config_dict: dictionary to update to the existing 'config' dict and ConfigParser object.
        :param overwrite_all: boolean, that sets if the existing 'config' dict and ConfigParser will be overwritten.
            If 'True' the existing 'config' dict and ConfigParser will be overwritten.
        :param overwrite_section_only: boolean, that sets if the specific 'config' dict and ConfigParser section
            will be overwritten, but not the whole configuration.
        :return:

        Usage Example:
        configparserw.ConfigParserWrapper(file_path=config_file_path).read_file_overwrite_with_update(
            config_dict=config_update_dict, overwrite_section_only=True)
        """

        self.initialize_config_parser()
        self.read_config_file()
        self.update_config(config_dict, overwrite_all=overwrite_all, overwrite_section_only=overwrite_section_only)
        self.write_to_file()

    def initialize_config_parser(self, include_getlist_method: bool = False):
        """
        Function initializes the 'configparser.ConfigParser()' object.

        :param include_getlist_method: boolean, that sets if 'configparser.ConfigParser()' should include converter
            for strings as lists as 'getlist' method. The default setting is not to use it.
            'getlist' can be used as:
                parsed_list: list = self.config_parser.getlist('section', 'key')
            Example config:
                [section]
                key = entry1, entry2
            Result:
                parsed_list = ['entry1', 'entry2']
        :return:
        """

        # Setting 'configparser' object.
        if not include_getlist_method:
            # Regular configparser initiation:
            self.config_parser = configparser.ConfigParser()
        else:
            # Using special initiation to read entries that contain lists.
            self.config_parser = configparser.ConfigParser(
                converters={'list': lambda x: [i.strip() for i in x.split(',')]})
            # Now we can use the list inside the file as:
            # [test_parameter]
            # names_list: a,list,of, and,1,2, 3,numbers
            # and get it as:
            # self.config_parser.getlist('test_parameter', 'names_list')
            # returning:
            # ['a', 'list', 'of', 'and', '1', '2', '3', 'numbers']

    def read_config_file(self, unicode_encoding: bool = False):
        """
        The function will use 'read()' method on config parser object to read the file from filesystem.
        :param unicode_encoding: boolean, that sets if "encoding='utf-8'" should be used to read files that contain
            unicode characters.
        :return:
        """
        # When using the "read()" method it gets the values of INI files to a dict type object.
        # When you initialize a "get()" method on a value that is non-existent, you will get an exception.

        if not self.config_parser:
            self.initialize_config_parser()

        if not unicode_encoding:
            self.config_parser.read(self.file_path)
        else:
            # Reading with 'utf-8' (non ansi languages):
            self.config_parser.read(self.file_path, encoding='utf-8')

        # If there are no sections in the configparser object, that means there really no sections, or the file
        # doesn't exist. ConfigParser doesn't check the file for existence.
        if not self.config_parser.sections():
            message = f'No sections in config file: {self.file_path}\n' \
                      f'Check if file exists.'
            raise FileNotFoundError(message)

    def convert_config_to_dict(self):
        """
        The function will convert the ConfigParser object into dictionary.
        """

        # Getting variables from configuration file.
        try:
            # {section_name: dict(config[section_name]) for section_name in config.sections()}
            for section_name in self.config_parser.sections():
                self.config.update({section_name: dict(self.config_parser[section_name])})
        except Exception:
            raise

    def convert_string_values(self, key_list: list, convert_type: str) -> None:
        """
        The function converts the 'key' string value of 'self.config' to specified 'convert_type'.

        Example for convert_type 'list':
            All strings that contain a comma
            character (',') will be split to list, if there are empty spaces between commas, they will be removed.
            Example string: '23, 34, 89,11, 5,20 , 21'
            Result list: ['23', '34', '89', '11', '5', '20', '21']

        :param key_list: list of keys that can be passed as tuple and string.
            Tuple: if single key passed as tuple, the first entry will act as 'section' and the second as 'key':
                ('section', 'key'). The value of expression will be converted to boolean: self.config[key[0]][key[1]].
            String: if single key passed as string, all keys with this name will be converted.
        :param convert_type: the type you want to convert string to. Available types:
            int: convert string line to integer.
            bool: convert string line to boolean from available to configparser database.
            list: convert comma separated string line to list of strings.
            list_of_int: convert comma separated string line to list of integers.
            path_relative_to_full: convert relative path to full filesystem path, adding 'config.ini' file's full
                directory to the beginning of the line with directory separator. If separator exists before the
                line, it will be removed.

                Example string line: \\request
                config.ini working path: d:\\scripts\\some_script
                Result of conversion: d:\\scripts\\some_script\\request

                If full path (absolute path) specified, nothing will be converted.
                Example: D:\\scripts\\some_script\\request
        :return: None.
        """

        def convert_string(value, convert_type):
            if convert_type == 'bool':
                # 'BOOLEAN_STATES' method of 'configparser' object has a dictionary of all boolean string keys to their
                # boolean representations in python. This is what 'getboolean()' method uses for conversion.
                # If the string 'value' in the 'keys()' of the 'BOOLEAN_STATES' method dictionary, then we'll fetch
                # its python boolean representation to the current key.
                if value in self.config_parser.BOOLEAN_STATES.keys():
                    return self.config_parser.BOOLEAN_STATES[value]
                else:
                    raise TypeError(f"The key provided doesn't contain string representation of a boolean.\n"
                                    f"Available types: {self.config_parser.BOOLEAN_STATES.keys()}")
            elif convert_type == 'int':
                return int(value)
            elif convert_type == 'list':
                if ',' in value:
                    # Split the string to list by comma ','.
                    result_list = value.split(',')
                    # Remove all the spaces before and after each string entry in the list.
                    for i, list_value in enumerate(result_list):
                        result_list[i] = result_list[i].removesuffix(' ').removeprefix(' ')

                    return result_list
                # If the line is empty, return empty list [] and not list with empty string [''].
                elif value == '':
                    return []
                else:
                    return [self.config[section][key]]
            # Convert string line to list of integers.
            elif convert_type == 'list_of_int':
                result_list = convert_string(value, convert_type='list')
                result_list = lists.convert_list_of_strings_to_integers(result_list)
                return result_list
            # Convert line if it is filesystem relative path to full path.
            elif convert_type == 'path_relative_to_full':
                # Remove last separator of the file path.
                self.directory_path = filesystem.remove_last_separator(self.directory_path)
                return filesystem.check_absolute_path___add_full(value, self.directory_path)

        # Iterate through all the keys in 'key_list'.
        for key in key_list:
            # If passed 'key' is a tuple of ('section', 'key').
            if isinstance(key, tuple):
                self.config[key[0]][key[1]] = convert_string(self.config[key[0]][key[1]], convert_type)
            # If passed 'key' is a string of key name only.
            elif isinstance(key, str):
                # Get all the sections and their values, each value is a dict (consists of one key and one value).
                for section, dicts in self.config.items():
                    # Since we don't know the key and value of each row, we'll use the 'items()' method.
                    for dict_key, value in dicts.items():
                        # If the key name of current iteration is the same as key passed, then convert the value.
                        if dict_key == key:
                            self.config[section][dict_key] = convert_string(value, convert_type)

    def _get_values_as_objects_configparser_api(self, **kwargs):
        """
        This function is for reference only of what can be done for parsing with 'ConfigParser' class and how
        the api works with exception examples.
        It is much easier to use 'convert_string_values' function.

        :param kwargs:
        :return:
        """

        try:
            # === Usage Examples:
            # Get string.
            self.config_parser.get('user', 'username')
            # Get integer.
            self.config_parser.getint('user', 'user_number')
            # Get boolean.
            # default_usage: bool = config.getboolean('advanced', 'default_usage')
            # Get list, after 'configparser.ConfigParser' manipulation.
            self.config_parser.getlist('tcp', 'port_list')
            # Get url that contains '%' character - don't interpolate it. Fetch as is or it will result in exception.
            self.config_parser.get('config', 'url', raw=True)
            # === Examples EOF.

        # If the "configparser" wasn't able to read the file (more than 255 character path or nonexistent) you will also
        # get "configparser.NoSectionError".
        except configparser.NoSectionError as exception_object:
            message = f"{exception_object}, in config file: {self.file_path}\n" \
                      f"Check if it exists.\n"
            print_api(message, error_type=True, color="red", **kwargs)
        except configparser.NoOptionError as exception_object:
            message = f"Option is missing in 'config.ini' file: {exception_object}"
            print_api(message, error_type=True, color="red", **kwargs)
        except KeyError as exception_object:
            message = f"Key is missing in 'config.ini' file: {exception_object}"
            print_api(message, error_type=True, color="red", **kwargs)

    def auto_convert_values(
            self, booleans: bool = True, convert_01_to_bool: bool = True, integers: bool = True,
            convert_section_key_list_to_list: list = None,
            skip_sections_list: list = None, skip_keys_list: list = None):
        """
        The function will convert all the string values to all the available formats.
        Currently supported: bool, list, integer.
        It is for experimental uses only, since it is hard to know what type of value really is in the string, and
        what your intentions are for this particular value. Better use 'convert_string_values' function
        to convert single keys.

        The function will not work well on complex configs and provided for reference only.
        Will not be maintained.

        :param booleans: boolean, sets if string value should be converted to boolean. All the conversion strings
            to their appropriate boolean values are taken from 'configparser.ConfigParser().BOOLEAN_STATES'.
        :param convert_01_to_bool: boolean, sets if '1' and '0' will be converted to booleans or integers.
        :param convert_section_key_list_to_list: list of tuples that contains ('section_string', 'key_string')
            that will be converted to list.

            All strings that contain a comma
            character (',') will be split to list, if there are empty spaces between commas, they will be removed.
            Example string: '23, 34, 89,11, 5,20 , 21'
            Result list: ['23', '34', '89', '11', '5', '20', '21']
        :param integers: boolean, sets if string value should be converted to integer. Integer conversion function
            comes after boolean conversion function. If, you have value of '1' or '0', they will be converted to
            boolean and not get to be converted as integers. If you set 'booleans=False', then '1' and '0' will be
            converted to integers. Same goes if you set 'convert_01_to_bool=False', meaning all the 'BOOLEAN_STATES'
            string values will be converted to booleans, but not '1' and '0' (they will be converted to integers).
        :param skip_sections_list: list of sections to skip.
        :param skip_keys_list: list of keys to skip.
        :return:
        """

        if not convert_section_key_list_to_list:
            convert_section_key_list_to_list = list()

        if not skip_sections_list:
            skip_sections_list = list()

        if not skip_keys_list:
            skip_keys_list = list()

        # Get all the sections and their values, each value is a dict (consists of one key and one value).
        for section, dicts in self.config.items():
            # Since we don't know the key and value of each row, we'll use the 'items()' method.
            for key, value in dicts.items():
                # If key and section are in the list conversion list.
                if (section, key) in convert_section_key_list_to_list:
                    # If the function did changes to the key, we can skip to next key.
                    if self.convert_string_values([(section, key)], "list"):
                        continue

                # If we should convert string value to boolean python object and also
                # the section is not in the section/key skip list.
                # Boolean section comes first, since it has '1' and '0' values in it.
                # If by all settings it changes the value to bool, we will not continue to integer conversion
                # since it will be overwritten.
                if booleans and section not in skip_sections_list and key not in skip_keys_list:
                    if (value == '1' or value == '0') and convert_01_to_bool:
                        # If the function did changes to the key, we can skip to next key.
                        if self.convert_string_values([(section, key)], "bool"):
                            continue

                # If we should convert string value to integer python object and also
                # the section is not in the section/key skip list.
                if integers and section not in skip_sections_list and key not in skip_keys_list:
                    # If the function did changes to the key, we can skip to next key.
                    if self.convert_string_values([(section, key)], "int"):
                        continue

from datetime import date

try:
    # This is a library in python 3.11 and above.
    import tomllib
except ModuleNotFoundError:
    # This is library from pypi.
    # noinspection PyPackageRequirements
    import tomli as tomllib

from . import file_io


class TomlValueNotImplementedError(Exception):
    pass


# noinspection PyUnusedLocal
@file_io.read_file_decorator
def read_toml_file(file_path: str,
                   file_mode: str = 'rb',
                   encoding=None,
                   file_object=None,
                   **kwargs) -> dict:
    """
    Read the toml file and return its content as dictionary.

    :param file_path: String with full file path to file.
    :param file_mode: string, file reading mode. Examples: 'r', 'rb'. Default is 'r'.
    :param encoding: string, encoding of the file. Default is 'None'.
    :param file_object: file object of the 'open()' function in the decorator. Decorator executes the 'with open()'
        statement and passes to this function. That's why the default is 'None', since we get it from the decorator.
    :return: dict.
    """

    # Read the file to variable
    return tomllib.load(file_object)


# noinspection PyUnusedLocal
@file_io.write_file_decorator
def write_toml_file(
        toml_content: dict,
        file_path: str,
        file_mode: str = 'w',
        encoding=None,
        file_object=None,
        **kwargs
) -> None:
    """
    Write the toml file with the specified content.

    :param toml_content: dict, content to write to the file.
    :param file_path: String with full file path to file.
    :param file_mode: string, file reading mode. Examples: 'w', 'wb'. Default is 'w'.
    :param encoding: string, encoding of the file. Default is 'None'.
    :param file_object: file object of the 'open()' function in the decorator. Decorator executes the 'with open()'
        statement and passes to this function. That's why the default is 'None', since we get it from the decorator.
    """

    # Write the file.
    file_object.write(dumps(toml_content))


def dumps(toml_dict: dict):
    """
    Dump the toml simple dictionary to string.
    The 'tomllib' library doesn't support dumping to string because of PEP680, so we will use this function.

    :param toml_dict: dict, toml dictionary to dump.
    :return: string, dumped toml dictionary.
    """

    def process_item(item_key, item_value):
        if isinstance(item_value, dict):
            toml_str = f'[{item_key}]\n'
            for sub_key, sub_value in item_value.items():
                toml_str += process_item(sub_key, sub_value)
            return toml_str
        elif isinstance(item_value, date):
            return f'{item_key} = {item_value.isoformat()}\n'
        elif item_value == '':
            return f"{item_key} = ''\n"
        elif isinstance(item_value, bool):
            return f'{item_key} = {str(item_value).lower()}\n'
        else:
            return f'{item_key} = {item_value}\n'

    toml_string = ''
    for key, value in toml_dict.items():
        toml_string += process_item(key, value)

    return toml_string


def update_toml_file_with_new_config(
        main_config_file_path: str,
        changes_config_file_path: str = None,
        changes_dict: dict = None,
        new_config_file_path: str = None
) -> None:
    """
    Update the old toml config file with the new values from the new toml config file.
    This will update only the changed values.
    If the values from the changes file aren't present in the main config file, they will not be added.

    :param main_config_file_path: string, path to the main config file that you want to use as the main reference.
        If you provide the 'new_config_file_path', then changes to the 'main_config_file_path' will be written there.
    :param changes_config_file_path: string, the config file path that have the changes.
        Only changed values will be updated to the 'main_config_file_path'.
    :param changes_dict: dict, the dictionary with the changes.
        Instead of providing the 'changes_config_file_path', you can provide only the dictionary with the changes.
    :param new_config_file_path: string, path to the new config file.
        If provided, the changes will be written to this file.
        If not, the changes will be written to the 'main_config_file_path'.
    """

    if not changes_config_file_path and not changes_dict:
        raise ValueError("You must provide either 'changes_config_file_path' or 'changes_dict'.")
    if changes_config_file_path and changes_dict:
        raise ValueError("You can't provide both 'changes_config_file_path' and 'changes_dict'.")

    with open(main_config_file_path, 'r') as file:
        main_config_file_text_lines: list = file.readlines()

    main_config_file_text_lines_backup: list = list(main_config_file_text_lines)

    # Read the new config file.
    main_config_file_dict: dict = read_toml_file(main_config_file_path)

    if not changes_dict:
        changes_dict: dict = read_toml_file(changes_config_file_path)

    # Update the config text lines.
    for category, settings in main_config_file_dict.items():
        if category not in changes_dict:
            continue

        for key, value in settings.items():
            # If the key is in the old config file, use the old value.
            if key not in changes_dict[category]:
                continue

            if main_config_file_dict[category][key] != changes_dict[category][key]:
                # Get the line of the current category line.
                current_category_line_index_in_text = None
                for current_category_line_index_in_text, line in enumerate(main_config_file_text_lines):
                    if f"[{category}]" in line:
                        break

                # Get the index inside the main config file dictionary of the current category.
                main_config_list_of_keys: list = list(main_config_file_dict.keys())
                current_category_index_in_main_config_dict = main_config_list_of_keys.index(category)

                try:
                    next_category_name = list(
                        main_config_file_dict.keys())[current_category_index_in_main_config_dict + 1]
                except IndexError:
                    next_category_name = list(main_config_file_dict.keys())[-1]

                next_category_line_index_in_text = None
                for next_category_line_index_in_text, line in enumerate(main_config_file_text_lines):
                    if f"[{next_category_name}]" in line:
                        break

                # In case the current and the next categories are the same and the last in the file.
                if next_category_line_index_in_text == current_category_line_index_in_text:
                    next_category_line_index_in_text = len(main_config_file_text_lines)

                string_to_check_list: list = list()
                if isinstance(value, bool):
                    string_to_check_list.append(f"{key} = {str(value).lower()}")
                elif isinstance(value, int):
                    string_to_check_list.append(f"{key} = {value}")
                elif isinstance(value, str):
                    string_to_check_list.append(f"{key} = '{value}'")
                    string_to_check_list.append(f'{key} = "{value}"')
                else:
                    raise TomlValueNotImplementedError(f"Value type '{type(value)}' not implemented.")

                # next_category_line_index_in_text = main_config_file_text_lines.index(f"[{next_category_name}]\n")
                # Find the index of this line in the text file between current category line and
                # the next category line.
                line_index = None
                found_line = False
                for line_index in range(current_category_line_index_in_text, next_category_line_index_in_text):
                    if found_line:
                        line_index = line_index - 1
                        break
                    for string_to_check in string_to_check_list:
                        if string_to_check in main_config_file_text_lines[line_index]:
                            found_line = True
                            break

                if found_line:
                    # If there are comments, get only them from the line. Comment will also get the '\n' character.
                    # noinspection PyUnboundLocalVariable
                    comment = main_config_file_text_lines[line_index].replace(string_to_check, '')

                    object_type = type(changes_dict[category][key])
                    if object_type == bool:
                        value_string_to_set = str(changes_dict[category][key]).lower()
                    elif object_type == str:
                        value_string_to_set = f"'{changes_dict[category][key]}'"
                    elif object_type == int:
                        value_string_to_set = str(changes_dict[category][key])

                    # noinspection PyUnboundLocalVariable
                    line_to_set = f"{key} = {value_string_to_set}{comment}"
                    # Replace the line with the old value.
                    main_config_file_text_lines[line_index] = line_to_set

                    main_config_file_dict[category][key] = changes_dict[category][key]

    if new_config_file_path:
        file_path_to_write = new_config_file_path
    else:
        file_path_to_write = main_config_file_path

    if not main_config_file_text_lines == main_config_file_text_lines_backup:
        # Write the final config file.
        with open(file_path_to_write, 'w') as file:
            file.writelines(main_config_file_text_lines)
    else:
        print("No changes to the config file.")

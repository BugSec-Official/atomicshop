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
    import re

    if not changes_config_file_path and not changes_dict:
        raise ValueError("You must provide either 'changes_config_file_path' or 'changes_dict'.")
    if changes_config_file_path and changes_dict:
        raise ValueError("You can't provide both 'changes_config_file_path' and 'changes_dict'.")

    with open(main_config_file_path, 'r') as file:
        main_config_file_text_lines: list = file.readlines()

    main_config_file_text_lines_backup: list = list(main_config_file_text_lines)

    # Read the main config file.
    main_config_file_dict: dict = read_toml_file(main_config_file_path)

    changes_config_file_text_lines = None
    if not changes_dict:
        with open(changes_config_file_path, 'r') as file:
            changes_config_file_text_lines = file.readlines()
        changes_dict = read_toml_file(changes_config_file_path)

    def _is_section_header(line: str) -> bool:
        # Matches: [section] or [section] # comment
        return re.match(r'^\s*\[[^\]]+\]\s*(#.*)?$', line) is not None

    def _get_section_bounds(lines: list, section_name: str = None):
        """
        Returns (start_index, end_index) boundaries for a section search.
        section_name=None means top-level (before first [section]).
        """
        if section_name is None:
            for i, line in enumerate(lines):
                if _is_section_header(line):
                    return 0, i
            return 0, len(lines)

        section_pattern = re.compile(rf'^\s*\[{re.escape(section_name)}\]\s*(#.*)?$')
        section_start = None

        for i, line in enumerate(lines):
            if section_pattern.match(line):
                section_start = i
                break

        if section_start is None:
            return None, None

        for i in range(section_start + 1, len(lines)):
            if _is_section_header(lines[i]):
                return section_start, i

        return section_start, len(lines)

    def _find_key_block(lines: list, key: str, section_name: str = None):
        """
        Returns (start_index, end_index) for the key block in the specified section.
        Handles single-line values and multi-line list blocks.
        """
        section_start, section_end = _get_section_bounds(lines, section_name)
        if section_start is None:
            return None

        key_pattern = re.compile(rf'^\s*{re.escape(key)}\s*=')

        for i in range(section_start, section_end):
            line = lines[i]

            # Skip commented lines
            if line.lstrip().startswith('#'):
                continue

            if not key_pattern.match(line):
                continue

            # Single-line key (not a list block)
            rhs = line.split('=', 1)[1]
            if '[' not in rhs:
                return i, i + 1

            # List block (possibly multi-line)
            bracket_depth = 0
            for j in range(i, section_end):
                bracket_depth += lines[j].count('[')
                bracket_depth -= lines[j].count(']')

                if bracket_depth <= 0:
                    return i, j + 1

            return i, section_end

        return None

    def _replace_list_block_from_changes(section_name: str, key: str) -> bool:
        """
        Copy the exact list block text (including comments) from the changes file into the main file.
        Returns True if replaced, False otherwise.
        """
        if changes_config_file_text_lines is None:
            return False

        src_block = _find_key_block(changes_config_file_text_lines, key, section_name)
        dst_block = _find_key_block(main_config_file_text_lines, key, section_name)

        if not src_block or not dst_block:
            return False

        src_start, src_end = src_block
        dst_start, dst_end = dst_block

        main_config_file_text_lines[dst_start:dst_end] = changes_config_file_text_lines[src_start:src_end]
        return True

    def _replace_scalar_line(section_name: str, key: str, new_value) -> bool:
        """
        Replace a scalar key=value line while preserving inline comments and indentation.
        """
        key_block = _find_key_block(main_config_file_text_lines, key, section_name)
        if not key_block:
            return False

        start, end = key_block
        if (end - start) != 1:
            return False  # Not a scalar line

        original_line = main_config_file_text_lines[start]

        # Preserve indentation
        indent = original_line[:len(original_line) - len(original_line.lstrip())]

        # Preserve inline comment (simple split, consistent with current function behavior)
        if '#' in original_line:
            line_without_comment, comment_part = original_line.split('#', 1)
            comment = '#' + comment_part
        else:
            line_without_comment = original_line
            comment = ''

        if isinstance(new_value, bool):
            value_string_to_set = str(new_value).lower()
        elif isinstance(new_value, str):
            value_string_to_set = f"'{new_value}'"
        elif isinstance(new_value, int):
            value_string_to_set = str(new_value)
        elif isinstance(new_value, float):
            value_string_to_set = str(new_value)
        else:
            raise TomlValueNotImplementedError(f"Value type '{type(new_value)}' not implemented.")

        # Ensure newline is preserved
        line_has_newline = original_line.endswith('\n')
        if comment:
            if line_has_newline and not comment.endswith('\n'):
                comment += '\n'
            new_line = f"{indent}{key} = {value_string_to_set}{comment}"
        else:
            new_line = f"{indent}{key} = {value_string_to_set}" + ('\n' if line_has_newline else '')

        main_config_file_text_lines[start] = new_line
        return True

    def _update_key(section_name: str, key: str, current_value, new_value):
        """
        Update a key in the specified section.
        Lists are copied as raw text from the changes file (to preserve comments).
        Scalars are replaced in-place.
        """
        if current_value == new_value:
            return

        if isinstance(current_value, list) and isinstance(new_value, list):
            # Best path: preserve comments and formatting from the changes config file.
            if _replace_list_block_from_changes(section_name, key):
                return

            # Fallback path (when only changes_dict is provided): rewrite list without comments.
            key_block = _find_key_block(main_config_file_text_lines, key, section_name)
            if not key_block:
                return

            start, end = key_block
            indent_match = re.match(r'^(\s*)', main_config_file_text_lines[start])
            indent = indent_match.group(1) if indent_match else ''

            new_block = [f"{indent}{key} = [\n"]
            for item in new_value:
                if isinstance(item, str):
                    item_value = f"'{item}'"
                elif isinstance(item, bool):
                    item_value = str(item).lower()
                elif isinstance(item, (int, float)):
                    item_value = str(item)
                else:
                    raise TomlValueNotImplementedError(f"List item type '{type(item)}' not implemented.")
                new_block.append(f"{indent}    {item_value},\n")
            new_block.append(f"{indent}]\n")

            main_config_file_text_lines[start:end] = new_block
            return

        _replace_scalar_line(section_name, key, new_value)

    # Iterate only over keys that exist in the main config (do not add new keys from changes).
    for top_level_key, top_level_value in main_config_file_dict.items():
        # Section/table
        if isinstance(top_level_value, dict):
            if top_level_key not in changes_dict or not isinstance(changes_dict[top_level_key], dict):
                continue

            for key, value in top_level_value.items():
                if key not in changes_dict[top_level_key]:
                    continue
                _update_key(top_level_key, key, value, changes_dict[top_level_key][key])

        # Top-level scalar/list key (e.g. devices = [ ... ])
        else:
            if top_level_key not in changes_dict:
                continue
            _update_key(None, top_level_key, top_level_value, changes_dict[top_level_key])

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
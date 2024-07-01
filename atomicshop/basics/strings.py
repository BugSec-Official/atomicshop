import fnmatch
import re
from pathlib import Path
import argparse

from . import lists
from ..print_api import print_api


def get_nth_character_from_start(input_string: str, nth: int):
    """
    Example:
        get_nth_character_from_start('123456789', 3)
    Result:
        '3'

    :param input_string: string, to get the character from.
    :param nth: integer, nth character to return.
    :return: string, nth character from the input string.
    """

    # Since the first character in the list (index) is '0', and 'nth' is human-readable (starts with '1'), we'll
    # subtract 1 from nth.
    nth = nth-1

    return input_string[nth]


def get_nth_character_from_end(input_string: str, nth: int):
    """
    Example:
        get_nth_character_from_end('123456789', 2)
    Result:
        '8'

    :param input_string: string, to get the character from.
    :param nth: integer, nth character from the end to return.
    :return: string, nth character from the end of the input string.
    """

    return input_string[-nth]


def cut_first_x_characters(input_string: str, number_of_characters: int):
    """
    Example:
        cut_first_x_characters('123456789', 5)
    Result:
        '6789'

    :param input_string: string, to cut characters from.
    :param number_of_characters: integer, number of characters to cut from beginning of the string.
    :return: string.
    """

    return input_string[number_of_characters:]


def get_last_x_characters(input_string: str, number_of_characters: int):
    # noinspection GrazieInspection
    """
    Example:
        get_last_x_characters('123456789', 2)
    Result:
        '89'

    :param input_string: string, to get characters from.
    :param number_of_characters: integer, number of characters to return from end of the string.
    :return:
    """

    return input_string[-number_of_characters:]


def split_at_string_and_return_after(input_string: str, split_string: str):
    """
    Example:
        split_at_string_and_return_after('123456789', '456')
    Result:
        '789'

    :param input_string: string, to split.
    :param split_string: string, to split the input string at.
    :return: string, after the split string.
    """

    # Split is done after the 'split_string'.
    parts = input_string.split(split_string)
    return parts[1]


def is_any_string_from_list_in_string(string_list: list, check_string: str) -> bool:
    """
    Function checks if any string from 'string_list' is in 'check_string'.

    Example:
        string_list = ['123', '456', '789']
        check_string = '123456789'
        is_any_string_from_list_in_string(string_list, check_string)
    Result:
        True

    :param string_list: list, of strings to check against.
    :param check_string: string, to check against.
    :return: boolean.
    """

    return any(test_string in check_string for test_string in string_list)


def match_pattern_against_string(
        pattern: str,
        check_string: str,
        case_insensitive: bool = False,
        prefix_suffix: bool = False
) -> bool:
    """
    Function checks the 'pattern' against 'check_string' and returns 'True' if pattern matches and 'False' if not.

    Example:
        pattern_string = "*ffmpeg*full_build.zip"
        check_string = "https://github.com/GyanD/codexffmpeg/releases/download/5.1.2/ffmpeg-5.1.2-full_build.zip"
        match_pattern_against_string(pattern_string, check_string)
    Result:
        True

    :param pattern: string, can include wildcards as '*'.
    :param check_string: string, to check the pattern against.
    :param case_insensitive: boolean, if 'True' will treat the 'pattern' and 'check_string' as case-insensitive.
    :param prefix_suffix: boolean, that sets if the function should return 'True' also for all the cases that wildcard
        in the beginning of the pattern and in the end of the pattern, since the default behavior of regex to return
        'False' on these cases.

        Example:
            pattern: *test
            check_string: testblabla
        Default regex behavior will return 'False' with 'prefix_suffix' switch set to 'True',
        this case will return 'True'. Same will go for:
        pattern: test*
            check_string: blablatest

        Why this is good?
        Let's say you have a python script 'example.py' and you want to find all the executed command lines,
        and you want to make sure that this was executed by 'python'. Your python is installed
        in 'c:\\Python310\\python.exe', and you want to match all the possible patterns of 'python' and 'example.py'.
        Pattern:
            *python*example.py
        You want to match 'True' for the next cases:
            python example.py
            c:\\Python310\\python.exe example.py

        Default regex behavior is to return 'False' on 'python example.py'.

    :return: boolean.
    """

    # 'fnmatch' is POSIX systems to match pattern in file names (example: file_name.exe), and this doesn't work well
    # on complex strings.
    # return fnmatch.fnmatch(check_string, pattern)

    # Determine the regex flags based on case_insensitive.
    flags = re.IGNORECASE if case_insensitive else 0

    def search_pattern(function_pattern):
        # Use regex to match the pattern.
        return re.search(fr'{function_pattern}', check_string, flags)

    wildcard_str: str = '*'
    wildcard_re: str = '.+'
    # wildcard_re: str = '.*'  # Adjusted to '.*' to match zero or more characters

    # Replace the wildcard string '*' with regex wildcard string '.+'.
    # In regex '.' is a wildcard, but only for 1 character, if you need more than 1 character you should add '+'.
    pattern_re = pattern.replace(wildcard_str, wildcard_re)
    pattern_no_wildcard = pattern.replace(wildcard_str, '')

    # Search for pattern, if found, return 'True'.
    if search_pattern(pattern_re):
        return True

    # 'regex' doesn't think that '.*' is a match for 'test', so we'll check for this case separately.
    if search_pattern(pattern_no_wildcard):
        return True

    # If it wasn't found in previous check,
    # then we'll continue checking without prefix and suffix if 'prefix_suffix' is 'True'.
    if prefix_suffix:
        wild_prefix: bool = False
        wild_suffix: bool = False

        # If wildcard is in the beginning of the pattern string.
        if pattern[0] == wildcard_str:
            wild_prefix = True
        # If wildcard is in the end of the pattern string.
        if pattern[-1] == wildcard_str:
            wild_suffix = True

        # If wildcard was found in the beginning of the pattern string.
        if wild_prefix:
            # Remove wildcard from the beginning of the pattern and try matching again.
            if search_pattern(pattern_re.removeprefix(wildcard_re)):
                return True
        # If wildcard was found in the end of the pattern string.
        elif wild_suffix:
            # Remove wildcard from the end of the pattern and try matching again.
            if search_pattern(pattern_re.removesuffix(wildcard_re)):
                return True
        # If wildcard was found in the beginning and the end of the pattern string.
        elif wild_prefix and wild_suffix:
            # Remove wildcard from the beginning and the end of the pattern and try matching again.
            if search_pattern(pattern_re.removeprefix(wildcard_re).removesuffix(wildcard_re)):
                return True

    return False


def match_list_of_patterns_against_string(
        patterns: list,
        check_string: str,
        case_insensitive: bool = False,
        prefix_suffix: bool = False
) -> bool:
    """
    Function checks each pattern in 'patterns' list against 'check_string' and returns 'True' if any pattern matches
    and 'False' if not.

    :param patterns: list, of string patterns to check against. May include wildcards.
    :param check_string: string, to check the pattern against.
    :param case_insensitive: boolean, if 'True' will treat the 'pattern' and 'check_string' as case-insensitive.
    :param prefix_suffix: boolean, that sets if the function should return 'True' also for all the cases that wildcard
        in the beginning of the pattern and in the end of the pattern, since the default behavior of regex to return
        'False' on these cases.

    :return: boolean.

    Check for all the examples the 'match_pattern_against_string' function.
    """

    for pattern in patterns:
        if match_pattern_against_string(
                pattern, check_string, case_insensitive=case_insensitive, prefix_suffix=prefix_suffix):
            return True

    return False


def match_pattern_against_list_of_strings(pattern: str, list_of_strings: list) -> list:
    """
    Function checks the 'pattern' against 'check_string' and returns 'True' if pattern matches and 'False' if not.

    Example:
        pattern_string = "*ffmpeg*full_build.zip"
        list_of_strings = ['ffmpeg-5.1.2-full_build.zip', 'ffmpeg-5.1.2-shared.zip']
        match_pattern_against_list_of_strings(pattern_string, list_of_strings)
    Result:
        ['ffmpeg-5.1.2-full_build.zip']

    :param pattern: string, can include wildcards as '*'.
    :param list_of_strings: list, of strings to check against.
    :return: list that contains values that match the pattern.
    """

    return fnmatch.filter(list_of_strings, pattern)


def contains_digit(string: str) -> bool:
    """ Function to check if string contains a digit. """
    return any(char.isdigit() for char in string)


def contains_letter(string: str) -> bool:
    """
    Function to check if string contains a letter. This is the fastest approach and doesn't use regex.
    https://stackoverflow.com/a/59301031
    """

    return string.upper().isupper()


def is_alphanumeric_only(string: str) -> bool:
    """
    Function to check if string contains only alphanumeric characters.
    """

    return string.isalnum()


def is_numeric_only(string: str) -> bool:
    """
    Function to check if string contains only numeric characters.
    """

    return string.isdigit()


def is_alphabetic_only(string: str) -> bool:
    """
    Function to check if string contains only alphabetic characters.
    """

    return string.isalpha()


def capitalize_first_letter(string: str) -> str:
    """
    Function capitalizes the first letter of the string.
    """

    # Take the first letter of the 'string[0]' (0 is the first letter of the 'string') and
    # capitalize it '.upper()' and add the rest of the letters
    # as is with 'string[1:]' (1 is the second letter of
    # the string 'string' and ':' means the rest of the string.

    return string[0].upper() + string[1:]


def replace_words_with_values_from_dict(
        sentence: str, dictionary: dict, contains: bool = False, case_insensitive: bool = False) -> str:
    """
    Function replaces words, which are keys with values from dictionary.
    The sentence is divided to list of words by spaces " ", and then each word is checked against the dictionary.
    So, your word in dictionary should not contain spaces " ".

    Example:
        sentence = 'Hello, my name is name1, and I am age years old.'
        dictionary = {'name1': 'John', 'age': '30'}
        replace_words_with_values_from_dict(sentence, dictionary)
    Result:
        'Hello, my name is John, and I am 30 years old.'

    :param sentence: string, to replace words in, should contain spaces " " between words.
    :param dictionary: dictionary, with words to replace and values to replace with.
    :param contains: boolean, if 'True' will try to replace words that are a part of another word.
        Example:
            sentence = 'Hello, my name is names987, and I am agesbla years old.'
            dictionary = {'name': 'John', 'age': '30'}
            replace_words_with_values_from_dict(sentence, dictionary, contains=True)
        Result:
            'Hello, my name is Johns987, and I am 30sbla years old.'
        With 'contains=False' the result would unchanged:
            'Hello, my name is names987, and I am agesbla years old.'
    :param case_insensitive: boolean, if 'True' will treat words in the 'sentence' as case-insensitive.
        Default is 'False'.
    :return: string, with replaced words.
    """

    # Split the sentence to words.
    sentence_parts: list = sentence.split(" ")

    # Replace exact words with values from dictionary.
    sentence_parts = lists.replace_elements_with_values_from_dict(
        sentence_parts, dictionary, contains=contains, case_insensitive=case_insensitive)
    joined_sentence: str = ' '.join(sentence_parts)

    return joined_sentence


def replace_strings_with_values_from_dict(string_to_replace: str, dictionary: dict) -> str:
    """
    Function replaces strings, which are keys with values from dictionary.

    :param string_to_replace: string, to replace words in.
    :param dictionary: dictionary, with words to replace and values to replace with.
    :return: string, with replaced words.

    Usage:
        sentence = 'test test'
        dictionary = {' ': '\ '}
        replace_words_with_values_from_dict(sentence, dictionary, contains=True)
    Result:
        'test\\ test'
    """

    for old, new in dictionary.items():
        string_to_replace = string_to_replace.replace(old, new)

    return string_to_replace


def multiple_splits_by_delimiters(full_string: str, delimiters: list) -> list[str]:
    """
    Function splits the string by multiple delimiters.
    :param full_string: string, to split.
    :param delimiters: list, of delimiters.
    :return: list of strings.
    """

    # Base case: no more delimiters, return the string itself in a list.
    if not delimiters:
        return [full_string]

    # Take the first delimiter.
    delimiter = delimiters[0]
    # Split the string on the current delimiter.
    split_strings = full_string.split(delimiter)
    # Get the remaining delimiters.
    remaining_delimiters = delimiters[1:]

    result = []
    for substring in split_strings:
        # Recursively call the whole function with each substring and the remaining delimiters.
        result.extend(multiple_splits_by_delimiters(substring, remaining_delimiters))
    return result


def check_if_suffix_is_in_string(string: str, suffix: str) -> bool:
    """
    Function checks if 'suffix' is in the end of 'string'.
    :param string: string, to check.
    :param suffix: string, to check.
    :return: boolean.
    """

    return string.endswith(suffix)


def convert_string_to_colon_separated(string: str, number_of_characters: int = 2) -> str:
    """
    Function converts string to colon separated string.
    :param string: string, to convert.
    :param number_of_characters: integer, number of characters to separate.

    Example:
        convert_string_to_colon_separated('1234567890', 2)
    Result:
        '12:34:56:78:90'

    :return: string.
    """

    return ':'.join([string[i:i+number_of_characters] for i in range(0, len(string), number_of_characters)])


def replace_string_in_file(
        file_path: str,
        old_string: str,
        new_string: str = None,
        find_only: bool = False,
        print_kwargs: dict = None
) -> list[int]:
    """
    Function replaces 'old_string' with 'new_string' in the file.
    :param file_path: string, path to the file.
    :param old_string: string, to replace.
    :param new_string: string, to replace with.
    :param find_only: boolean, if 'True' will only find the 'old_string' and return line numbers where it was found.
    :param print_kwargs: dict, the print_api arguments.
    :return: list of integers, line numbers where the 'old_string' was found.
    """

    if not find_only and new_string is None:
        raise ValueError("The 'new_string' string must be provided if 'find_only' is False.")

    changed_lines = []

    # Read the file content
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    # Search for the old string and either replace or just track line numbers
    for index, line in enumerate(lines, start=1):
        if old_string in line:
            changed_lines.append(index)
            if not find_only:
                lines[index - 1] = line.replace(old_string, new_string)

    # If not in find-only mode, overwrite the file with the replaced content
    if not find_only:
        with open(file_path, 'w', encoding='utf-8') as file:
            file.writelines(lines)

    # Output the relevant line numbers
    print_api(f"Target string found on the following lines: {changed_lines}", **(print_kwargs or {}))
    return changed_lines


def replace_string_in_file_main_argparse():
    """
    Main function for the 'replace_string_in_file' function.
    You can use this function as a command line tool.
    Example:
        Create a file 'replace_string_in_file.py' with the next content:
        ```
        from atomicshop.basics import strings

        if __name__ == '__main__':
            strings.replace_string_in_file_main_argparse()
        ```
    """

    parser = argparse.ArgumentParser(description="Replace string in file.")
    parser.add_argument("file_path", type=Path, help="Path to the file.")
    parser.add_argument("old_string", type=str, help="Old string to replace.")
    parser.add_argument("--new_string", '-n', help="New string to replace with.")
    parser.add_argument(
        '--find_only', '-f', action='store_true',
        help='Only output lines where the old string is found, without replacing.')

    args = parser.parse_args()

    replace_string_in_file(
        file_path=args.file_path,
        old_string=args.old_string,
        new_string=args.new_string,
        find_only=args.find_only
    )

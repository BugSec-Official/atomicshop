import fnmatch
import re

from . import lists


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


def match_pattern_against_string(pattern: str, check_string: str, prefix_suffix: bool = False) -> bool:
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

    def search_pattern(function_pattern):
        # Use regex to match the pattern.
        return re.search(fr'{function_pattern}', check_string)

    wildcard_str: str = '*'
    wildcard_re: str = '.+'

    # Replace the wildcard string '*' with regex wildcard string '.+'.
    # In regex '.' is a wildcard, but only for 1 character, if you need more than 1 character you should add '+'.
    pattern_re = pattern.replace(wildcard_str, wildcard_re)

    # Search for pattern, if found, return 'True'.
    if search_pattern(pattern_re):
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


def replace_words_with_values_from_dict(
        sentence: str, dictionary: dict, contains: bool = False, case_insensitive: bool = False) -> str:
    """
    Function replaces words, which are keys with values from dictionary.

    Example:
        sentence = 'Hello, my name is name, and I am age years old.'
        dictionary = {'name': 'John', 'age': '30'}
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

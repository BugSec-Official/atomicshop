def remove_duplicates(list_instance: list):
    # One of the fastest methods.
    seen = set()
    seen_add = seen.add
    return [x for x in list_instance if not (x in seen or seen_add(x))]


def sort_list(list_instance: list) -> None:
    """
    List is an instance. 'sort()' method - sorts the list in place. Meaning you don't have to return anything.

    :param list_instance: list.
    """

    list_instance.sort()


def convert_list_of_strings_to_integers(list_instance: list) -> list:
    return [int(i) for i in list_instance]


def get_difference(list1, list2):
    # This is one of the fastest approaches: https://stackoverflow.com/a/3462202
    s = set(list2)
    return [x for x in list1 if x not in s]


def replace_elements_with_values_from_dict(
        list_instance: list, dictionary: dict, contains: bool = False, case_insensitive: bool = False) -> list:
    """
    Function exchanges elements from list with elements from dictionary.

    Example:
        list_instance = ['a', 'b', 'c']
        dictionary = {'a': 'd', 'b': 'e', 'c': 'f'}
        exchange_elements_from_dict(list_instance, dictionary)
    Result:
        ['d', 'e', 'f']

    :param list_instance: list.
    :param dictionary: dictionary.
    :param contains: boolean, if 'True' will try to replace words that are a part of another word.
        Example:
            list_instance = ['Hello', 'my', 'name', 'is', 'names987', 'and', 'I', 'am', 'agesbla', 'years', 'old']
            dictionary = {'name': 'John', 'age': '30'}
            replace_words_with_values_from_dict(sentence, dictionary, contains=True)
        Result:
            ['Hello', 'my', 'name', 'is', 'Johns987', 'and', 'I', 'am', '30sbla', 'years', 'old']
        With 'contains=False' the result would unchanged:
            ['Hello', 'my', 'name', 'is', 'names987', 'and', 'I', 'am', 'agesbla', 'years', 'old']
    :param case_insensitive: boolean, if 'True' will treat words in the list as case-insensitive. Default is 'False'.
    :return: list.
    """

    converted_list: list = list()
    for word in list_instance:
        if case_insensitive:
            word = word.lower()

        word = dictionary.get(word, word)

        if contains:
            # convert if the word contains key of the dictionary.
            for key in dictionary.keys():
                if key in word:
                    word = word.replace(key, dictionary[key])

        converted_list.append(word)

    return converted_list

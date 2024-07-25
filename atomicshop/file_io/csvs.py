import csv
from typing import Tuple, List

from .file_io import read_file_decorator
from . import file_io


@read_file_decorator
def read_csv_to_list_of_dicts_by_header(
        file_path: str,
        file_mode: str = 'r',
        encoding=None,
        header: list = None,
        file_object=None,
        **kwargs
) -> Tuple[List, List | None]:
    """
    Function to read csv file and output its contents as list of dictionaries for each row.
    Each key of the dictionary is a header field.

    Example:
        CSV file:
        name,age,city
        John,25,New York

        Output:
        [{'name': 'John', 'age': '25', 'city': 'New York'}]

    :param file_path: String with full file path to json file.
    :param file_mode: string, file reading mode. Examples: 'r', 'rb'. Default is 'r'.
    :param encoding: string, encoding of the file. Default is 'None'.
    :param header: list, list of strings that will be the header of the CSV file. Default is 'None'.
        None: the header from the CSV file will be used. The first row of the CSV file will be the header.
            Meaning, that the first line will be skipped and the second line will be the first row of the content.
        List: the list will be used as header.
            All the lines of the CSV file will be considered as content.
    :param file_object: file object of the 'open()' function in the decorator. Decorator executes the 'with open()'
        statement and passes to this function. That's why the default is 'None', since we get it from the decorator.
    :return: tuple(list of entries, header(list of cell names)).
    """

    # The header fields will be separated to list of "csv_reader.fieldnames".

    # Create CSV reader from 'input_file'. By default, the first row will be the header if 'fieldnames' is None.
    csv_reader = csv.DictReader(file_object, fieldnames=header)

    # Create list of dictionaries out of 'csv_reader'.
    csv_list: list = list(csv_reader)

    header = csv_reader.fieldnames

    return csv_list, header


@read_file_decorator
def read_csv_to_list_of_lists(
        file_path: str,
        file_mode: str = 'r',
        encoding=None,
        exclude_header_from_content: bool = False,
        file_object=None,
        **kwargs
) -> Tuple[List, List | None]:
    """
    Function to read csv file and output its contents as list of lists for each row.

    Example:
        CSV file:
        name,age,city
        John,25,New York

        Output:
        [['name', 'age', 'city'], ['John', '25', 'New York']]

    :param file_path: String with full file path to json file.
    :param file_mode: string, file reading mode. Examples: 'r', 'rb'. Default is 'r'.
    :param encoding: string, encoding of the file. Default is 'None'.
    :param exclude_header_from_content: Boolean, if True, the header will be excluded from the content.
    :param file_object: file object of the 'open()' function in the decorator. Decorator executes the 'with open()'
        statement and passes to this function. That's why the default is 'None', since we get it from the decorator.
    :param kwargs: Keyword arguments for 'read_file' function.
    :return: list.
    """

    # Read CSV file to list of lists.
    csv_reader = csv.reader(file_object)

    csv_list = list(csv_reader)

    # Get the header if there is only something in the content.
    if csv_list:
        header = csv_list[0]
    else:
        header = []

    if exclude_header_from_content and csv_list:
        csv_list.pop(0)

    return csv_list, header


def write_list_to_csv(
        file_path: str,
        content_list: list,
        mode: str = 'w'
) -> None:
    """
    This function got dual purpose:
    1. Write list object that each iteration of it contains list object with same length.
    2. Write list object that each iteration of it contains dict object with same keys and different values.
    The dictionary inside the function will be identified by the first iteration of the list.
    Other objects (inside the provided list) than dictionary will be identified as regular objects.

    :param file_path: Full file path to CSV file.
    :param content_list: List object that each iteration contains dictionary with same keys and different values.
    :param mode: String, file writing mode. Default is 'w'.
    :return: None.
    """

    with open(file_path, mode=mode, newline='') as csv_file:
        if len(content_list) > 0 and isinstance(content_list[0], dict):
            # Treat the list as list of dictionaries.
            header = content_list[0].keys()

            # Create CSV writer.
            writer = csv.DictWriter(csv_file, fieldnames=header, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

            # Write header.
            writer.writeheader()
            # Write list of dits as rows.
            writer.writerows(content_list)
        # Else, treat the list as list of lists.
        else:
            # Create CSV writer.
            writer = csv.writer(csv_file)
            # Write list of lists as rows.
            writer.writerows(content_list)


def get_header(file_path: str, print_kwargs: dict = None) -> list:
    """
    Function to get header from CSV file.

    :param file_path: Full file path to CSV file.
    :param print_kwargs: Keyword arguments dict for 'print_api' function.

    :return: list of strings, each string is a header field.
    """

    if not print_kwargs:
        print_kwargs = dict()

    # Get the first line of the file as text, which is the header.
    header = file_io.read_file(file_path, read_to_list=True, **print_kwargs)[0]
    # Split the header to list of keys.
    header = header.split(',')
    return header

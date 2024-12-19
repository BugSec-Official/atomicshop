import csv
import io
from typing import Tuple, List

from . import file_io


@file_io.read_file_decorator
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


@file_io.read_file_decorator
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
        content_list: list,
        file_path: str,
        mode: str = 'w',
        encoding: str = None
) -> None:
    """
    This function got dual purpose:
    1. Write list object that each iteration of it contains list object with same length.
    2. Write list object that each iteration of it contains dict object with same keys and different values.
    The dictionary inside the function will be identified by the first iteration of the list.
    Other objects (inside the provided list) than dictionary will be identified as regular objects.

    :param content_list: List object that each iteration contains dictionary with same keys and different values.
    :param file_path: Full file path to CSV file.
    :param mode: String, file writing mode. Default is 'w'.
    :param encoding: String, encoding of the file. Default is 'None'.
        Example: 'utf-8', 'utf-16', 'cp1252'.
    :return: None.
    """

    with open(file_path, mode=mode, newline='', encoding=encoding) as csv_file:
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


def _escape_csv_value_ref(text):
    """
    FOR REFERENCE ONLY, better use csv module to do it natively.
    Function to escape text for CSV file.
    This function escapes commas (,) and double quotes (") for csv cell (between commas).

    Example:
        test1 = 'test1'
        test2 = 'test,2'
        test3 = 'test3,"3",3'

        csv_line = f'{escape_csv_value(test1)},{escape_csv_value(test2)},{escape_csv_value(test3)}'

        Output: 'test1,"test,2","test3,""3"",3"'
    """

    if '"' in text:
        text = text.replace('"', '""')  # Escape double quotes
    if ',' in text or '"' in text:
        text = f'"{text}"'  # Enclose in double quotes if there are commas or double quotes
    return text


def escape_csv_value(value):
    """
    Function to escape text for CSV file.
    This function escapes commas (,) and double quotes (") for csv cell (between commas).

    Example:
        test1 = 'test1'
        test2 = 'test,2'
        test3 = 'test3,"3",3'

        csv_line = f'{escape_csv_value(test1)},{escape_csv_value(test2)},{escape_csv_value(test3)}'

        Output: 'test1,"test,2","test3,""3"",3"'
    """
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow([value])
    return output.getvalue().strip()


def escape_csv_line_to_string(csv_line: list) -> str:
    """
    Function to escape list of strings for CSV file.
    This function escapes commas (,) and double quotes (") for csv cell (between commas).

    Example:
        test1 = 'test1'
        test2 = 'test,2'
        test3 = 'test3,"3",3'

        csv_line = escape_csv_line_to_string([test1, test2, test3])

        Output:
        csv_line == 'test1,"test,2","test3,""3"",3"'
    """

    # Prepare the data as a list of lists
    data = [csv_line]

    # Use StringIO to create an in-memory file-like object
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Write the data to the CSV writer
    writer.writerows(data)

    # Get the CSV string from the StringIO object, Strip to remove any trailing newlines.
    csv_line = output.getvalue().strip()

    return csv_line


def escape_csv_line_to_list(csv_line: list) -> list:
    """
    Function to escape list of strings for CSV file.
    This function escapes commas (,) and double quotes (") for csv cell (between commas).

    Example:
        test1 = 'test1'
        test2 = 'test,2'
        test3 = 'test3,"3",3'

        csv_entries_list = escape_csv_line_to_list([test1, test2, test3])

        Output:
        csv_entries_list == ['test1', '"test,2"', '"test3,""3"",3"']
    """

    result_csv_entries: list = []
    for entry in csv_line:
        result_csv_entries.append(escape_csv_value(entry))

    return result_csv_entries


def get_number_of_cells_in_string_line(line: str) -> int:
    """
    Function to get number of cells in CSV line.

    :param line: String, line of CSV file.
    :return: int, number of cells in the line.
    """

    # Create CSV reader from 'input_file'. By default, the first row will be the header if 'fieldnames' is None.
    csv_reader = csv.reader([line])

    # Get the first row of the CSV file.
    csv_list = list(csv_reader)

    # Get the number of cells in the first row.
    number_of_cells = len(csv_list[0])

    return number_of_cells

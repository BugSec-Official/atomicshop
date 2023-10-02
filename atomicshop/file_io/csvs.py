import csv
from typing import Tuple, List

from .file_io import read_file_decorator


@read_file_decorator
def read_csv_to_list(file_path: str,
                     file_mode: str = 'r',
                     encoding=None,
                     header: list = None,
                     file_object=None,
                     **kwargs) -> Tuple[List, List | None]:
    """
    Function to read csv file and output its contents as list of dictionaries for each row.

    :param file_path: String with full file path to json file.
    :param file_mode: string, file reading mode. Examples: 'r', 'rb'. Default is 'r'.
    :param encoding: string, encoding of the file. Default is 'None'.
    :param header: list, list of strings that will be the header of the CSV file. Default is 'None'.
        If you want to use the header from the CSV file, use 'None'. In this case, the first row of the CSV file will
        be the header.
    :param file_object: file object of the 'open()' function in the decorator. Decorator executes the 'with open()'
        statement and passes to this function. That's why the default is 'None', since we get it from the decorator.
    :return: list.
    """

    # The header fields will be separated to list of "csv_reader.fieldnames".

    # Create CSV reader from 'input_file'. By default, the first row will be the header if 'fieldnames' is None.
    csv_reader = csv.DictReader(file_object, fieldnames=header)

    # Create list of dictionaries out of 'csv_reader'.
    csv_list: list = list(csv_reader)

    header = csv_reader.fieldnames

    return csv_list, header


def write_list_to_csv(csv_list: list, csv_filepath: str) -> None:
    """
    Function to write list object that each iteration of it contains dict object with same keys and different values.

    :param csv_list: List object that each iteration contains dictionary with same keys and different values.
    :param csv_filepath: Full file path to CSV file.
    :return: None.
    """

    with open(csv_filepath, mode='w') as csv_file:
        # Create header from keys of the first dictionary in list.
        header = csv_list[0].keys()
        # Create CSV writer.
        writer = csv.DictWriter(csv_file, fieldnames=header, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        # Write header.
        writer.writeheader()
        # Write list of dits as rows.
        writer.writerows(csv_list)

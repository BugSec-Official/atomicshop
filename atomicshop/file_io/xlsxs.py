import pandas

from .file_io import write_file_decorator


@write_file_decorator
def write_xlsx(
        spread_sheets: dict,
        file_path: str,
        file_mode: str = 'w',
        index: bool = False,
        file_object=None,
        **kwargs
) -> None:
    """
    Write data to xlsx file. Including several spreadsheets if specified.

    :param file_path: string, full path to the file to write.
    :param spread_sheets: dict. Each dict is a spreadsheet. The keys are the names of the sheets and the
        values are the dicts to write to the sheets.

        Example:
            spread_sheets = {
                'sheet1': {
                    'col1': [1, 2, 3],
                    'col2': [4, 5, 6]
                },
                'sheet2': {
                    'col1': [7, 8, 9],
                    'col2': [10, 11, 12]
                }
            }
    :param file_mode: string, file writing mode. Examples: 'x', 'w', 'wb'.
    :param index: boolean, if True, the index of the data frame will be written to the file on the left-most column.
        The index meaning that each row will have a number, starting from 0.
    :param file_object: file object of the 'open()' function in the decorator. Decorator executes the 'with open()'
        statement and passes to this function. That's why the default is 'None', since we get it from the decorator.
    :return:
    """

    # Create dict of data frames.
    spread_sheets = {sheet_name: pandas.DataFrame(sheet_data) for sheet_name, sheet_data in spread_sheets.items()}

    # Save the file.
    with pandas.ExcelWriter(file_path, engine='openpyxl') as writer:
        for sheet_name, sheet_data in spread_sheets.items():
            sheet_data.to_excel(writer, sheet_name=sheet_name, index=index)

    # # Create the writer object.
    # writer = pandas.ExcelWriter(file_path, engine='xlsxwriter')
    #
    # # Iterate through the spreadsheets.
    # for sheet_name, sheet_data in spread_sheets.items():
    #     # Write the sheet.
    #     sheet_data.to_excel(writer, sheet_name=sheet_name)
    #
    # # Save the file.
    # writer.save()

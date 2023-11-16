from docx import Document
from docx.opc.exceptions import PackageNotFoundError

from .. import filesystem, config_init
from . import file_io
from ..print_api import print_api


def get_hyperlinks(docx_path):
    """
    Get all hyperlinks from a docx file.
    :param docx_path: string, path to the docx file.
    :return: list of strings, hyperlinks.
    """

    hyperlinks: list = list()

    try:
        doc = Document(docx_path)
    # If the file is empty, it will raise an exception.
    # The same exception will rise if the file is opened in Word.
    except PackageNotFoundError:
        print_api(f"File is empty or opened in Word: {docx_path}", color="red", error_type=True)
        return hyperlinks

    for paragraph in doc.paragraphs:
        if not paragraph.hyperlinks:
            continue
        for hyperlink in paragraph.hyperlinks:
            hyperlinks.append(hyperlink.address)

    return hyperlinks


def search_for_hyperlink_in_files(directory_path: str, hyperlink: str, relative_paths: bool = False):
    """
    Search for a hyperlink in all the docx files in the specified directory.
    :param directory_path: string, path to the directory with docx files.
    :param hyperlink: string, hyperlink to search for.
    :param relative_paths: boolean, if True, the function will return relative paths to the files and not the full
        file paths. Example: 'content\file.docx' instead of 'D:/content/file.docx' if you specified 'D:/' as
        'directory_path'.
    :return:

    Main function example:
        from atomicshop import filesystem
        from atomicshop.file_io import docxs
        from atomicshop import file_io

        directory_path = r"D:/directory_with_docx_files"
        script_directory: str = filesystem.get_file_directory(__file__)
        string_file_path: str = script_directory + r"/hyperlink.txt"
        hyperlink: str = file_io.read_file(string_file_path)

        found_in_files = docxs.search_for_hyperlink_in_files(directory_path, hyperlink, relative_paths=True)

        for found_file in found_in_files:
            print(found_file)

        input('press Enter')
    """

    if not filesystem.check_directory_existence(directory_path):
        raise NotADirectoryError(f"Directory doesn't exist: {directory_path}")

    # Get all the docx files in the specified directory.
    files = filesystem.get_file_paths_and_relative_directories(
        directory_path, file_name_check_pattern="*.docx", relative_file_name_as_directory=True)

    found_in_files: list = list()
    for file_path in files:
        hyperlinks = get_hyperlinks(file_path['path'])
        if hyperlink in hyperlinks:
            found_in_files.append(file_path)

    if relative_paths:
        result_list = list()
        for found_file in found_in_files:
            result_list.append(found_file['relative_dir'])
    else:
        result_list = found_in_files

    return result_list


def search_for_hyperlink_in_files_interface_main(script_directory: str = None):
    """
    Main function for the interface of the 'search_for_hyperlink_in_files' function.
    :param script_directory: string, path to the script directory. Default is None. If None, the function will
        get the working directory instead.

    Main function example:
        from atomicshop.file_io import docxs

        def main():
            docxs.search_for_hyperlink_in_files_interface_main()

        if __name__ == '__main__':
            main()
    """

    # Create the 'config.toml' file if it doesn't exist. Manually constructing the TOML content.
    toml_dict = {
        'directory_path': '',
        'hyperlink': '',
        'relative_paths': True
    }

    config_init.write_config(config=toml_dict, script_directory=script_directory)

    # Get the config file content.
    config = config_init.get_config(script_directory)

    found_in_files = search_for_hyperlink_in_files(
        config['directory_path'], config['hyperlink'], relative_paths=config['relative_paths'])

    for found_file in found_in_files:
        print(found_file)

    input('press Enter')

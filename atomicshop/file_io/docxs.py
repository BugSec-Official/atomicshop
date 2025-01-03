from docx import Document
from docx.opc.exceptions import PackageNotFoundError

from .. import filesystem, config_init
from ..print_api import print_api


def get_hyperlinks(docx_path):
    """
    Get all hyperlinks from a docx file.
    :param docx_path: string, path to the docx file.
    :return: list of strings, hyperlinks.
    """

    hyperlinks: list[dict] = list()

    try:
        doc = Document(docx_path)
    # If the file is empty, it will raise an exception.
    # The same exception will rise if the file is opened in Word.
    except PackageNotFoundError:
        print_api(f"File is not DOCX format or opened in Word: {docx_path}", color="red", error_type=True)
        return hyperlinks

    for paragraph in doc.paragraphs:
        if not paragraph.hyperlinks:
            continue
        for hyperlink in paragraph.hyperlinks:
            # Hyperlinks are stored in docx (document.xml) without the fragment part.
            # Fragment is the anchor of the link, for example: 'https://www.example.com#anchor'.
            # So the hyperlink.address is stored as 'https://www.example.com'.
            # And the fragment is stored in the hyperlink.fragment as 'anchor'.
            # For the full hyperlink, we need to concatenate the address and the fragment.
            # If there is no anchor in the link the fragment will be empty string ('').
            # Basically, we don't need to add the fragment to the hyperlink if it's empty, we can just use the url.
            # if hyperlink.fragment:
            #     hyperlinks.append(hyperlink.address + "#" + hyperlink.fragment)
            hyperlinks.append({
                'url': hyperlink.url,
                'text': hyperlink.text
            })

    return hyperlinks


def search_for_hyperlink_in_files(directory_path: str, hyperlink: str, relative_paths: bool = False):
    # noinspection GrazieInspection
    """
        Search for a hyperlink in all the docx files in the specified directory.
        :param directory_path: string, path to the directory with docx files.
        :param hyperlink: string, hyperlink to search for.
        :param relative_paths: boolean, if True, the function will return relative paths to the files and not the full
            file paths. Example: 'content\file.docx' instead of 'D:/content/file.docx' if you specified 'D:/' as
            'directory_path'.
        :return:

        Main function example:
            import os
            from atomicshop import filesystem
            from atomicshop.file_io import docxs, file_io


            # Usage
            directory_path = r"D:/directory_with_docx_files"
            script_directory: str = filesystem.get_file_directory(__file__)
            string_file_path: str = script_directory + os.sep + r"hyperlink.txt"
            hyperlink: str = file_io.read_file(string_file_path)

            found_in_files = docxs.search_for_hyperlink_in_files(directory_path, hyperlink, relative_paths=True)

            for found_file in found_in_files:
                print(found_file)

            input('press Enter')
        """

    if not filesystem.is_directory_exists(directory_path):
        raise NotADirectoryError(f"Directory doesn't exist: {directory_path}")

    # Get all the docx files in the specified directory.
    files = filesystem.get_paths_from_directory(
        directory_path, get_file=True, file_name_check_pattern="*.docx",
        add_relative_directory=True, relative_file_name_as_directory=True)

    found_in_files: list[dict] = list()
    for file_path in files:
        doc_hyperlinks = get_hyperlinks(file_path.path)
        for doc_link in doc_hyperlinks:
            if hyperlink in doc_link['url']:
                if relative_paths:
                    path: str = file_path.relative_dir
                else:
                    path: str = file_path.path

                found_in_files.append({
                    'path':path,
                    'link':doc_link['url'],
                    'text':doc_link['text']
                })

    return found_in_files


def search_for_hyperlink_in_files_interface_main(script_directory: str = None):
    """
    Main function for the interface of the 'search_for_hyperlink_in_files' function.
    :param script_directory: string, path to the script directory. Default is None. If None, the function will
        get the working directory instead.

    Main function example:
        from atomicshop.file_io import docxs

        def main():
            docxs.search_for_hyperlink_in_files_interface_main()

        # Create the 'config.toml' file if it doesn't exist.
        # Run the script the first time in order to create empty TOML.
        # Note: relative_paths: boolean, if True, the function will return relative paths to the files and not the full
        #         file paths. Example: 'content\file.docx' instead of 'D:/content/file.docx' if you specified 'D:/' as
        #         'directory_path'.
        # hyperlink = 'https://www.example.com'
        # directory_path = 'C:/where/to/look/for/docxs'
        # relative_paths = True

        if __name__ == '__main__':
            main()
    """

    # Create the 'config.toml' file if it doesn't exist. Manually constructing the TOML content.
    toml_dict = {
        'hyperlink': '',
        'directory_path': '',
        'relative_paths': True
    }

    config_init.write_config(config=toml_dict, script_directory=script_directory)

    # Get the config file content.
    config = config_init.get_config(script_directory)

    found_in_files = search_for_hyperlink_in_files(
        config['directory_path'], config['hyperlink'], relative_paths=config['relative_paths'])

    print_api(f"Found [{len(found_in_files)}] links:", color="blue")

    for index, found_file in enumerate(found_in_files):
        print_api(f"[{index+1}]", print_end="", color="green")
        print_api(f" {found_file['path']}")
        print_api(f" {found_file['link']}", color="cyan")
        print_api(f" {found_file['text']}", color="orange")

    input('[*] Press [Enter] to exit...')

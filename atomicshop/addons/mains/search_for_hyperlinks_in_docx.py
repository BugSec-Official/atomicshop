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
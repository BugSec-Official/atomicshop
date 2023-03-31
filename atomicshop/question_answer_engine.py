# Basic Imports.
import os
import sys
import json

# Custom class imports.
from atomicshop.filesystem import check_file_existence


class QAEngine:
    """
    QAEngine class is responsible for 'qa.json' file import.
    """

    def __init__(self):
        self.qa_filename: str = "qa.json"
        self.qa_dictionary: dict = dict()

    def open(self, script_directory: str) -> None:
        # Get 'qa.json' full path.
        qa_fullpath: str = script_directory + os.sep + self.qa_filename
        # Check if it exists.
        if not check_file_existence(qa_fullpath):
            print(f'File non-existent: {qa_fullpath}')
            sys.exit()

        # Import QA json file.
        with open(qa_fullpath, mode="r", encoding="utf-8") as input_file:
            self.qa_dictionary = json.load(input_file)

# v1.0.1 - 26.03.2023 23:50
import sys
import argparse
from argparse import RawTextHelpFormatter


class ArgparseWrapper:
    """
    # Usage in the main:
    args = ArgparseWrapper().parser_arguments
    # Defining variables to each argument
    input_path: str = args.input
    output_path: str = args.output
    """

    def __init__(self):
        self.application_short: str = 'pbtkMultiFile'
        self.application_full: str = 'pbtk Multi File wrapper'
        self.version: str = '1.0.0'
        self.description: str = 'Find ".proto" files in directory of binaries.'
        self.description_full: str = f'{self.application_full} v{self.version}\n' \
                                     f'Description: {self.description}'
        self.usage_variable: str = "%(prog)s [-h] -in folder_with_binary_files -out full_path_to_output_files\n" \
                                   "Input or Output path shouldn't end with separator. Example: '\\'."
        self.parser_arguments = None

        # Execute argparse.
        self.define_argparse()

    # Function to define argument parser
    def define_argparse(self):
        # Create the parser
        # formatter_class=RawTextHelpFormatter: shows raw text and not the default argparse text parsing.
        parser = argparse.ArgumentParser(description=self.description_full,
                                         usage=self.usage_variable,
                                         formatter_class=RawTextHelpFormatter)

        # Add arguments
        parser.add_argument('-in', '--input',
                            action='store', type=str, metavar='PATH_TO_FOLDER_WITH_BINARY_FILES',
                            required=True,
                            help='Provide full path to folder that contains binary files.')
        parser.add_argument('-out', '--output', action='store', type=str, metavar='PATH_TO_SAVE_EXPORTED_FILES',
                            required=True,
                            help='Provide full path where you want to store exported file.')

        # A problem before executing 'parse_args()'.
        # If we get directory path as argument, on windows we can get a path that ends with backslash:
        # C:\Users\user\documents\
        # This is the default behaviour of windows when copying path of only the directory.
        # When the path contains spaces, we need to pass it with double quotes:
        # "C:\Users\user\documents\some folder name\another\"
        # When python receives the arguments from CMD they get already parsed, meaning python can do nothing about it.
        # From input:
        # python_script.py -in "C:\some folder name\another\" -out "C:\some folder name\another1\"
        # You will get output:
        # ['python_script.py',
        #   '-in',
        #   'C:\some folder name\another" -out C:\some',
        #   'folder',
        #   'name\another1"]
        # 'parse_args()' gets its input from 'sys.argv'. Meaning, you will need to do some manipulations on that
        # Before executing the argparse argument parsing.
        # Probably the fix should be individual for each case.
        # The simplest solution though is to tell the user not to use backslash in the end of directory in case
        # of exception.

        try:
            # Execute parse_args()
            parsed_arguments = parser.parse_args()
        # The only thing that you can catch on without modifying Argparse code is 'SystemExit' exception.
        # You can also provide just 'except' without anything, which isn't the best practice.
        # Another fix would be to use
        # argparse.ArgumentParser(exit_on_error=False)
        # But as of python 3.10.8 it is not working yet.
        except SystemExit as exception_object:
            print('======================================')
            print('[*] Info: Error in provided arguments.')
            print('[*] Tip: Check if you have backslash "\\" in the end of folder path, if so remove it.')
            print('======================================')
            sys.exit()

        # if the folder path argument in the middle will have backslash "\" it will cause an exception.
        # If the backslash will be in the end, it will not cause exception, but the string will end with double quotes.
        parsed_arguments.input = parsed_arguments.input.replace('"', '')
        parsed_arguments.output = parsed_arguments.output.replace('"', '')

        self.parser_arguments = parsed_arguments

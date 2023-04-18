import sys
import argparse
from argparse import RawTextHelpFormatter


class ArgparseWrapper:
    """
    Usage in the main:
        args = ArgparseWrapper().parser_arguments

    Defining variables to each argument
        input_path: str = args.input
        output_path: str = args.output
    """

    def __init__(self):
        self.application_short: str = 'SupS'
        self.application_full: str = 'Super Script'
        self.version: str = '1.0.0'
        self.description: str = 'Super Script for super stuff.'
        self.description_full: str = f'{self.application_full} v{self.version}\n' \
                                     f'Description: {self.description}'
        self.usage_variable: str = "%(prog)s [-h] -in folder_with_binary_files -out full_path_to_output_files\n" \
                                   "Input or Output path shouldn't end with separator. Example: '\\'."
        self.parser = None
        self.parsed_arguments = None

        # Execute argparse.
        self.create_parser()
        self.add_arguments()
        self.parse_arguments()
        self.after_parse_manipulations()

    def create_parser(self):
        # Create parser.
        # formatter_class=RawTextHelpFormatter: shows raw text and not the default argparse text parsing.
        self.parser = argparse.ArgumentParser(description=self.description_full,
                                              usage=self.usage_variable,
                                              formatter_class=RawTextHelpFormatter)

    def add_arguments(self) -> None:
        """
        Function to define argument parser.

        :return: None
        """

        # Add arguments
        self.parser.add_argument('-in', '--input',
                                 action='store', type=str, metavar='PATH_TO_FOLDER_WITH_BINARY_FILES',
                                 required=True,
                                 help='Provide full path to folder that contains binary files.')
        self.parser.add_argument('-out', '--output', action='store', type=str, metavar='PATH_TO_SAVE_EXPORTED_FILES',
                                 required=True,
                                 help='Provide full path where you want to store exported file.')

        self.parser.add_argument('--site', type=str, required=True)
        # Switch '--noincognito' will set argument 'incognito' to boolean 'False'.
        self.parser.add_argument('--noincognito', dest='incognito', action='store_false')

        # Add a group of different switches ('--firefox', '--chrome', '--edge') that will set an argument 'browser'
        # (args.browser) with string constant.
        feature_parser = self.parser.add_mutually_exclusive_group(required=False)
        feature_parser.add_argument('--firefox', dest='browser', action='store_const', const='firefox')
        feature_parser.add_argument('--chrome', dest='browser', action='store_const', const='chrome')
        feature_parser.add_argument('--edge', dest='browser', action='store_const', const='edge')
        # If none of the switches from the group is selected, then defaults of 'chromium' will be used for
        # argument 'browser'.
        self.parser.set_defaults(browser='chromium')

    def parse_arguments(self):
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
            self.parsed_arguments = self.parser.parse_args()
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

    def after_parse_manipulations(self):
        # if the folder path argument in the middle will have backslash "\" it will cause an exception.
        # If the backslash will be in the end, it will not cause exception, but the string will end with double quotes.
        self.parsed_arguments.input = self.parsed_arguments.input.replace('"', '')
        self.parsed_arguments.output = self.parsed_arguments.output.replace('"', '')

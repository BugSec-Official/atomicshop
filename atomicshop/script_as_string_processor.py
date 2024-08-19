"""Loading resources using stdlib importlib.resources APIs (Python 3.7+)
https://docs.python.org/3/library/importlib.html#module-importlib.resources"""
import importlib.resources
from typing import Literal

from .print_api import print_api


class ScriptAsStringProcessor:
    def __init__(self):
        self.resources_directory_name: str = 'ssh_scripts'

        # string variable that is going to be exchanged with variable from main script.
        self.exchange_input_variable_string: str = "exchange_input_variable"
        self.script_string: str = str()

    def read_script_to_string(
            self,
            script_file_name: Literal['process_from_port', 'process_from_ipv4']
    ):
        self.script_string = importlib.resources.read_text(
            f'{__package__}.{self.resources_directory_name}',
            f'{script_file_name}.py')

        return self

    def put_variable_into_script_string(self, input_variable: any, print_kwargs: dict = None):
        # Defining variables
        function_result: str = str()

        if self.exchange_input_variable_string in self.script_string:
            # string.replace(old, new, count)
            # old – old substring you want to replace.
            # new – new substring which would replace the old substring.
            # count – the number of times you want to replace the old substring with the new substring. (Optional)
            # We want to replace our string only one time in the beginning.
            function_result = self.script_string.replace(self.exchange_input_variable_string, str(input_variable), 1)
        else:
            message = f"The script string provided doesn't contain {self.exchange_input_variable_string}"
            print_api(message, error_type=True, logger_method='error', **print_kwargs)

        return function_result

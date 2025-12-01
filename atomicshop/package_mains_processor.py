"""Loading resources using stdlib importlib.resources APIs (Python 3.7+)
https://docs.python.org/3/library/importlib.html#module-importlib.resources"""
import importlib.resources
from contextlib import redirect_stdout
import io
import subprocess
import sys


class PackageMainsProcessor:
    def __init__(
            self,
            script_file_stem: str = None
    ):
        self.script_file_stem: str = script_file_stem
        self.resources_directory_name: str = 'a_mains'

    def get_resource_path(self) -> str:
        return f'{__package__}.{self.resources_directory_name}'

    def read_script_file_to_string(self) -> str:
        script_string = importlib.resources.read_text(self.get_resource_path(), f'{self.script_file_stem}.py')

        return script_string

    def execute_script_file(
            self,
            function_name: str = 'main',
            args: tuple = None,
            kwargs: dict = None
    ) -> str:
        """
        Execute a script file from the package resources and get result as string.

        :param function_name: Name of the function to call within the script.
        :param args: Tuple of positional arguments to pass to the function.
        :param kwargs: Dictionary of keyword arguments to pass to the function.

        :return: Output of the script execution as a string.
        """

        if not args:
            args = ()
        if not kwargs:
            kwargs = {}

        module_name = f"{self.get_resource_path()}.{self.script_file_stem}"  # script_file_name WITHOUT ".py"

        module = importlib.import_module(module_name)

        with io.StringIO() as buffer, redirect_stdout(buffer):
            callable_function = getattr(module, function_name)
            callable_function(*args, **kwargs)

            output = buffer.getvalue()

        return output

    def execute_script_with_subprocess(
            self,
            arguments: list = None
    ) -> tuple[str, str, int]:
        """
        Execute a script file from the package resources using subprocess and get result as string.
        :param arguments: Dictionary of arguments to pass to the script.
            Example: ['--port', '8080', '-v']
        :return: Tuple containing (stdout, stderr, returncode).
        """

        # script_file_name WITHOUT ".py"
        module_name = f"{self.get_resource_path()}.{self.script_file_stem}"

        command = [sys.executable, "-m", module_name]
        if arguments:
            command.extend(arguments)

        result = subprocess.run(command, capture_output=True, text=True)

        return result.stdout, result.stderr, result.returncode

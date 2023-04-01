# v1.0.3 - 01.04.2021 - 15:30
import os
import datetime
import tempfile
import functools

from .print_api import print_api
from .inspect_wrapper import get_target_function_default_args_and_combine_with_current


def _write_tempfile_object_decorator(function_name):
    @functools.wraps(function_name)
    def wrapper_write_tempfile_object_decorator(*args, **kwargs):
        # Put 'args' into 'kwargs' with appropriate key.
        # args, kwargs = put_args_to_kwargs(function_name, *args, **kwargs)
        args, kwargs = get_target_function_default_args_and_combine_with_current(function_name, *args, **kwargs)

        try:
            # Create temp file with 'tempfile' naming.
            with tempfile.TemporaryFile() as output_file:
                # Get temp directory.
                temp_directory: str = tempfile.gettempdir()
                # Get tempfile name.
                tempfile_name: str = output_file.name
                # Full tempfile path.
                tempfile_path: str = temp_directory + os.sep + tempfile_name
                print_api(message=f"Created temp file: {tempfile_path}", **kwargs)

                # Pass the 'output_file' object to kwargs that will pass the object to the executing function.
                kwargs['file_object'] = output_file
                # Since our 'kwargs' has already all the needed arguments, we don't need 'args'.
                function_name(**kwargs)

            print_api(f'Removed tempfile: {tempfile_path}', **kwargs)
        # This exception is valid for file mode 'x' - Exclusive writing.
        # except FileExistsError as exception_object:
        #     message = f"Can't write file: {kwargs['file_path']}\n" \
        #               f"File exists, you should enable force/overwrite mode."
        #     print_api(message, error_type=True, logger_method='critical', **kwargs)
        except Exception:
            raise

    return wrapper_write_tempfile_object_decorator


@ _write_tempfile_object_decorator
def _write_tempfile_from_file_object(file_object=None, **kwargs):
    return


class TempFile:
    def __init__(self, file_name: str = str()):
        self.directory = tempfile.gettempdir()
        self.file_name: str = file_name

        if not self.file_name:
            self.file_name: str = f'temp_{datetime.datetime.now()}'

        self.file_path: str = self.directory + os.sep + self.file_name

    def remove(self):
        os.remove(self.file_path)

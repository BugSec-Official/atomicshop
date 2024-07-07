from pathlib import Path

from ... import filesystem, hashing
from ... import diff_check
from ...print_api import print_api


class FileCheck:
    """
    Class for file monitoring.
    """
    def __init__(self, change_monitor_instance):
        self.diff_checker = None
        self.change_monitor_instance = None
        self.store_original_file_path = None

        if not change_monitor_instance.input_file_name:
            change_monitor_instance.input_file_name = Path(change_monitor_instance.check_object).name
            change_monitor_instance.input_file_name = change_monitor_instance.input_file_name.lower()
            change_monitor_instance.input_file_name = (
                change_monitor_instance.input_file_name.replace(' ', '_').replace('.', '_'))
            change_monitor_instance.input_file_name = f'{change_monitor_instance.input_file_name}.txt'

        input_file_path = (
            str(Path(change_monitor_instance.input_directory, change_monitor_instance.input_file_name)))

        # If 'store_original_object' is True, create filename for the store original object.
        if change_monitor_instance.object_type_settings['store_original_object']:
            store_original_file_name: str = f'ORIGINAL_{Path(change_monitor_instance.check_object).name}'
            self.store_original_file_path = str(Path(change_monitor_instance.input_directory, store_original_file_name))

        self.diff_checker = diff_check.DiffChecker(
            return_first_cycle=False,
            operation_type='single_object',
            input_file_path=input_file_path,
            check_object_display_name=f'{change_monitor_instance.input_file_name}|{change_monitor_instance.object_type}'
        )
        self.diff_checker.initiate_before_action()
        self.change_monitor_instance = change_monitor_instance

    def execute_cycle(self, print_kwargs: dict = None):
        """
        This function executes the cycle of the change monitor: hash.

        :param print_kwargs: print_api kwargs.
        :return: List of dictionaries with the results of the cycle.
        """

        return_list = list()

        self._get_hash()

        # Check if the object was updated.
        result, message = self.diff_checker.check_string(
            print_kwargs=print_kwargs)

        # If the object was updated, print the message in yellow color, otherwise print in green color.
        if result:
            print_api(message, color='yellow', **print_kwargs)
            # create_message_file(message, self.__class__.__name__, logger=self.logger)

            return_list.append(message)
        else:
            print_api(message, color='green', **print_kwargs)

        return return_list

    def _get_hash(self):
        # Copy the file to the original object directory.
        if self.store_original_file_path:
            filesystem.copy_file(self.change_monitor_instance.check_object, self.store_original_file_path)

        # Get hash of the file.
        hash_string = hashing.hash_file(self.change_monitor_instance.check_object)

        # Set the hash string to the 'check_object' variable.
        self.diff_checker.check_object = hash_string

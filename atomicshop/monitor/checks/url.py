from pathlib import Path

from ... import hashing, urls
from ... import diff_check
from ...print_api import print_api


class UrlCheck:
    """
    Class for file monitoring.
    """
    def __init__(self, change_monitor_instance):
        self.diff_checker = None
        self.change_monitor_instance = None
        self.store_original_file_path = None
        self.get_method = None

        # Extract the method name from the object type.
        self.get_method = change_monitor_instance.object_type.split('_', 1)[1]

        if not change_monitor_instance.input_file_name:
            change_monitor_instance.input_file_name = (
                urls.url_parser(change_monitor_instance.check_object))['directories'][-1]
            change_monitor_instance.input_file_name = change_monitor_instance.input_file_name.lower()
            change_monitor_instance.input_file_name = f'{change_monitor_instance.input_file_name}.txt'

        input_file_path = (
            str(Path(change_monitor_instance.input_directory, change_monitor_instance.input_file_name)))

        # If 'store_original_object' is True, create filename for the store original object.
        if change_monitor_instance.object_type_settings['store_original_object']:
            # Add extension to the file name.
            extension: str = str()
            if 'playwright' in self.get_method:
                extension = self.get_method.split('_')[1]
            elif self.get_method == 'urllib':
                extension = 'html'

            store_original_file_name: str = Path(change_monitor_instance.input_file_name).stem
            store_original_file_name = f'{store_original_file_name}.{extension}'
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

        self._get_hash(print_kwargs=print_kwargs)

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

    def _get_hash(self, print_kwargs: dict = None):
        """
        The function will get the hash of the URL content.

        :param print_kwargs: print_api kwargs.
        """
        # Get hash of the url. The hash will be different between direct hash of the URL content and the
        # hash of the file that was downloaded from the URL. Since the file has headers and other information
        # that is not part of the URL content. The Original downloaded file is for reference only to see
        # what was the content of the URL at the time of the download.
        hash_string = hashing.hash_url(
            self.change_monitor_instance.check_object, get_method=self.get_method,
            path=self.store_original_file_path, print_kwargs=print_kwargs)

        # Set the hash string to the 'check_object' variable.
        self.diff_checker.check_object = hash_string

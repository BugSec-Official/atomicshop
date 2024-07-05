from typing import Literal, Union
from pathlib import Path

from .checks import dns, network, hash, process_running
from .. import filesystem, scheduling


DNS__DEFAULT_SETTINGS = {
    'learning_mode_create_unique_entries_list': True,
    'learning_hours': 24,                                   # 0 - the learning will never stop.
    'alert_about_missing_entries_after_learning': False,
    'alert_about_missing_entries_always': True,
    'create_alert_statistics': True,
    'statistics_rotation_hours': 'midnight'                  # 'midnight' or float of hours
}

FILE__URL__DEFAULT_SETTINGS = {
    'store_original_object': False
}


class ChangeMonitor:
    """
    Class monitors different features for changes. All the available features are in 'checks' folder.
    """
    def __init__(
            self,
            check_object: any = None,
            input_file_name: str = None,
            input_statistics_file_name: str = None,
            input_directory: str = None,
            input_file_write_only: bool = True,
            object_type: Union[
                Literal[
                    'file',
                    'dns',
                    'network',
                    'process_running',
                    'url_urllib',
                    'url_playwright_html',
                    'url_playwright_pdf',
                    'url_playwright_png',
                    'url_playwright_jpeg'],
                None] = None,
            object_type_settings: dict = None
    ):
        """
        :param object_type: string, type of object to check. The type must be one of the following:
            'file': 'check_object_list' must contain strings of full path to the file.
            'dns': 'check_object_list' will be none, since the DNS events will be queried from the system.
            'network': 'check_object_list' will be none, since the network events will be queried from the system.
            'process_running': 'check_object_list' must contain strings of process names to check if they are running.
                Example: ['chrome.exe', 'firefox.exe']
                No file is written.
            'url_urllib': 'check_object_list' must contain strings of full URL to a web page. The page will be
                downloaded using 'urllib' library in HTML.
            'url_playwright_html': 'check_object_list' must contain strings of full URL to a web page. The page will
                be downloaded using 'playwright' library in HTML.
            'url_playwright_pdf': 'check_object_list' must contain strings of full URL to a web page. The page will
                be downloaded using 'playwright' library in PDF.
            'url_playwright_png': 'check_object_list' must contain strings of full URL to a web page. The page will
                be downloaded using 'playwright' library in PNG.
            'url_playwright_jpeg': 'check_object_list' must contain strings of full URL to a web page. The page will
                be downloaded using 'playwright' library in JPEG.
        :param object_type_settings: dict, specific settings for the object type.
            'dns': Check the default settings example in 'DNS__DEFAULT_SETTINGS'.
        :param check_object: The object to check if changed.
            'dns': empty.
            'network': empty.
            'process_running': list of strings, process names to check if they are running.
            'file': string, full path to the file.
            'url_*': string, full URL to a web page.
        :param input_directory: string, full directory path for storing input files for current state of objects,
            to check later if this state isn't updated. If this variable is left empty, all the content will be saved
            in memory and input file will not be used.
            If the file is not specified, the update of an object will be checked
            only during the time that the script is running. Meaning, each time the script starts from beginning
            it will measure the object from the start as the script didn't know what it was before running.
            The problem? If you want to check that a program updated and the computer restarted, you will not
            know about that if the input file wasn't written. Since, the script will not know what happened before
            restart and what hash value the file had before the update.
        :param input_file_name: string, of file name to save as. If file name wasn't specified, we will
            generate one. Each function will generate the file name based on the object type and the object name.
        :param input_file_write_only: boolean,
            True: read the input file only once on script start, afterward read the variable from the memory, and write
                to the input file whether the object was updated.
            False: write to input file each time there is an update, and read each check cycle from the file and not
                from the memory.
        :param store_original_object: boolean, if True, the original object will be stored on the disk inside
        'Original' folder, inside 'input_directory'.
        :param operation_type: string, type of operation to perform. The type must be one of the following:
            'hit_statistics': will only store the statistics of the entries in the input file.
            'all_objects': disable the DiffChecker features, meaning any new entries will be emitted as is.
            None: will use the default operation type, based on the object type.
        :param hit_statistics_input_file_rotation_cycle_hours:
            float, the amount of hours the input file will be rotated in the 'hit_statistics' operation type.
            str, (only 'midnight' is valid), the input file will be rotated daily at midnight.
            This is valid only for the 'hit_statistics' operation type.
        :param hit_statistics_enable_queue: boolean, if True, the statistics queue will be enabled.
        :param new_objects_hours_then_difference: float, currently works only for the 'dns' object_type.
            This is only for the 'new_objects' operation type.
            If the object is not in the list of objects, it will be added to the list.
            If the object is in the list of objects, it will be ignored.
            After the specified amount of hours, new objects will not be added to the input file list, so each new
            object will be outputted from the function. This is useful for checking new objects that are not
            supposed to be in the list of objects, but you want to know about them.

        If 'input_directory' is not specified, the 'input_file_name' is not specified, and
        'generate_input_file_name' is False, then the input file will not be used and the object will be stored
        in memory. This means that the object will be checked only during the time that the script is running.
        """

        # === Initialize Main variables ====================================

        self.check_object: any = check_object
        self.input_file_name: str = input_file_name
        self.input_statistics_file_name: str = input_statistics_file_name
        self.input_directory: str = input_directory
        self.input_file_write_only: bool = input_file_write_only
        self.object_type = object_type
        self.object_type_settings: dict = object_type_settings

        # === Additional variables ========================================

        # self.original_object_directory = None
        # self.original_object_file_path = None

        # # If 'store_original_object' is True, create directory for original object.
        # if self.store_original_object:
        #     # Make path for original object.
        #     self.original_object_directory = filesystem.add_object_to_path(
        #         self.input_directory, 'Original')
        #     # Create directory if it doesn't exist.
        #     filesystem.create_directory(self.original_object_directory)
        #
        # Initialize objects for DNS and Network monitoring.

        self.checks_instance = None
        self._setup_object()

    def _setup_object(self):
        if self.object_type == 'file' or 'url_' in self.object_type:
            self.checks_instance = hash
        if self.object_type == 'dns':
            self.checks_instance = dns

            if not self.object_type_settings:
                self.object_type_settings = DNS__DEFAULT_SETTINGS
        elif self.object_type == 'network':
            self.checks_instance = network
        elif self.object_type == 'process_running':
            self.checks_instance = process_running

        self.checks_instance.setup_check(self)

    def check_cycle(self, print_kwargs: dict = None):
        """
        Checks if file was updated.
        :param print_kwargs: dict, that contains all the arguments for 'print_api' function.
        :return: None
        """

        return_list = self.checks_instance.execute_cycle(print_kwargs=print_kwargs)

        return return_list

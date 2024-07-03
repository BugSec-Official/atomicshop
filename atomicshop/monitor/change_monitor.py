from typing import Literal, Union
import queue

from .checks import dns, network, hash, process_running
from .. import filesystem, scheduling
from ..diff_check import DiffChecker


class ChangeMonitor:
    """
    Class monitors different features for changes. All the available features are in 'checks' folder.
    """
    def __init__(
            self,
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
            check_object_list: list = None,
            input_file_directory: str = None,
            input_file_name: str = None,
            generate_input_file_name: bool = False,
            input_file_write_only: bool = True,
            store_original_object: bool = False,
            operation_type: Literal[
                'hit_statistics',
                'all_objects'] = None,
            input_file_rotation_cycle_hours: Union[
                float,
                Literal['midnight'],
                None] = None,
            enable_statistics_queue: bool = False
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
        :param check_object_list: list of objects to check if it changed. The list can contain as many objects as
            needed and can contain only one object.
            The list can be left empty if the object type is 'dns', 'network_sockets'.
        :param input_file_directory: string, full directory path for storing input files for current state of objects,
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
        'Original' folder, inside 'input_file_directory'.
        :param operation_type: string, type of operation to perform. The type must be one of the following:
            'hit_statistics': will only store the statistics of the entries in the input file.
            'all_objects': disable the DiffChecker features, meaning any new entries will be emitted as is.
            None: will use the default operation type, based on the object type.
        :param input_file_rotation_cycle_hours:
            float, the amount of hours the input file will be rotated in the 'hit_statistics' operation type.
            str, (only 'midnight' is valid), the input file will be rotated daily at midnight.
            This is valid only for the 'hit_statistics' operation type.
        :param enable_statistics_queue: boolean, if True, the statistics queue will be enabled.

        If 'input_file_directory' is not specified, the 'input_file_name' is not specified, and
        'generate_input_file_name' is False, then the input file will not be used and the object will be stored
        in memory. This means that the object will be checked only during the time that the script is running.
        """

        # =================== Exception section ============================
        if not input_file_directory and store_original_object:
            raise ValueError('ERROR: [input_file_directory] must be specified if [store_original_object] is True.')

        if not input_file_directory and generate_input_file_name:
            raise ValueError('ERROR: [input_file_directory] must be specified if [generate_input_file_name] is True.')

        if not input_file_directory and input_file_name:
            raise ValueError('ERROR: [input_file_directory] must be specified if [input_file_name] is specified.')

        if input_file_name and generate_input_file_name:
            raise ValueError(
                'ERROR: [input_file_name] and [generate_input_file_name] cannot be both specified and True.')

        if operation_type:
            if operation_type not in ['hit_statistics', 'all_objects']:
                raise ValueError(
                    'ERROR: [operation_type] must be one of the following: "hit_statistics", "all_objects".')

        if input_file_rotation_cycle_hours and operation_type != 'hit_statistics':
            raise ValueError("[input_file_rotation_cycle] can be specified only for 'hit_statistics' operation type.")

        # === EOF Exception section ========================================
        # === Initialize Main variables ====================================

        if not check_object_list:
            check_object_list = list()

        self.object_type = object_type
        self.check_object_list: list = check_object_list
        self.input_file_directory: str = input_file_directory
        self.input_file_name: str = input_file_name
        self.generate_input_file_name: bool = generate_input_file_name
        self.input_file_write_only: bool = input_file_write_only
        self.store_original_object: bool = store_original_object
        self.operation_type = operation_type
        self.input_file_rotation_cycle_hours = input_file_rotation_cycle_hours
        self.enable_statistics_queue = enable_statistics_queue

        # === EOF Initialize Main variables ================================
        # === Initialize Secondary variables ===============================

        # The 'diff_check' will store the list of DiffChecker classes.
        self.diff_check_list: list = list()

        # If 'check_object_list' is a list, loop through it and create a DiffChecker object for each object.
        if self.check_object_list:
            for index in range(len(self.check_object_list)):
                self.diff_check_list.append(
                    DiffChecker(
                        input_file_write_only=self.input_file_write_only,
                        operation_type=self.operation_type,
                        input_file_rotation_cycle_hours=self.input_file_rotation_cycle_hours,
                        enable_statistics_queue=self.enable_statistics_queue
                    )
                )
        # Else, if 'check_object_list' is None, create a DiffChecker object only once.
        else:
            self.diff_check_list.append(
                DiffChecker(
                    input_file_write_only=self.input_file_write_only,
                    operation_type=self.operation_type,
                    input_file_rotation_cycle_hours=self.input_file_rotation_cycle_hours,
                    enable_statistics_queue=self.enable_statistics_queue
                )
            )

        self.input_file_path = None
        self.original_object_directory = None
        self.original_object_file_path = None

        # If 'store_original_object' is True, create directory for original object.
        if self.store_original_object:
            # Make path for original object.
            self.original_object_directory = filesystem.add_object_to_path(
                self.input_file_directory, 'Original')
            # Create directory if it doesn't exist.
            filesystem.create_directory(self.original_object_directory)

        self.first_cycle = True

        # Initialize objects for DNS and Network monitoring.
        self.fetch_engine = None
        self.thread_looper = scheduling.ThreadLooper()

    def _set_input_file_path(self, check_object_index: int = 0):
        if self.first_cycle:
            # If 'input_file_directory' and 'input_file_name' are specified, we'll use a filename to store.
            if self.input_file_directory and self.input_file_name:
                self.input_file_path = filesystem.add_object_to_path(
                    self.input_file_directory, self.input_file_name)

            # Set the input file path.
            self.diff_check_list[check_object_index].input_file_path = self.input_file_path

    def check_cycle(self, print_kwargs: dict = None):
        """
        Checks if file was updated.
        :param print_kwargs: dict, that contains all the arguments for 'print_api' function.
        :return: None
        """

        return_list = list()

        if (
                self.object_type == 'file' or
                'url_' in self.object_type):
            return_list = hash._execute_cycle(self, print_kwargs=print_kwargs)
        if self.object_type == 'dns':
            return_list = dns._execute_cycle(self, print_kwargs=print_kwargs)
        elif self.object_type == 'network':
            return_list = network._execute_cycle(self, print_kwargs=print_kwargs)
        elif self.object_type == 'process_running':
            return_list = process_running._execute_cycle(self, print_kwargs=print_kwargs)

        # Set 'first_cycle' to False, since the first cycle is finished.
        if self.first_cycle:
            self.first_cycle = False

        return return_list

    def run_loop(self, interval_seconds=0, print_kwargs: dict = None):
        self.thread_looper.run_loop(
            self.check_cycle, kwargs={'print_kwargs': print_kwargs}, interval_seconds=interval_seconds)

    def emit_from_loop(self):
        return self.thread_looper.emit_from_loop()

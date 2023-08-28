from .. import hashing, filesystem, urls
from ..diff_check import DiffChecker
from ..print_api import print_api
from ..etw.dns_trace import DnsTrace
from ..basics import list_of_dicts


class ChangeMonitor:
    """
    Class monitors different features for changes. All the available features are in 'checks' folder.
    """
    def __init__(
            self,
            object_type: str,
            check_object_list: list = None,
            input_file_directory: str = None,
            input_file_name: str = None,
            generate_input_file_name: bool = False,
            input_file_write_only: bool = True,
            store_original_object: bool = False,
    ):
        """
        :param object_type: string, type of object to check. The type must be one of the following:
            'dns': 'check_object_list' will be none, since the DNS events will be queried from the system.
            'file': 'check_object_list' must contain strings of full path to the file.
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

        # === EOF Exception section ========================================
        # === Initialize Main variables ====================================

        if not check_object_list:
            check_object_list = list()

        self.object_type: str = object_type
        self.check_object_list: list = check_object_list
        self.input_file_directory: str = input_file_directory
        self.input_file_name: str = input_file_name
        self.generate_input_file_name: bool = generate_input_file_name
        self.input_file_write_only: bool = input_file_write_only
        self.store_original_object: bool = store_original_object

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
                    )
                )
        # Else, if 'check_object_list' is None, create a DiffChecker object only once.
        else:
            self.diff_check_list.append(
                DiffChecker(
                    input_file_write_only=self.input_file_write_only,
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

        # Initialize objects for DNS monitoring.
        self.fetch_engine = None

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
        # Loop through all the objects to check.
        for check_object_index, check_object in enumerate(self.check_object_list):
            if self.object_type == 'file':
                # Get the hash of the object.
                self._get_file_hash(check_object_index, check_object, print_kwargs=print_kwargs)
            elif self.object_type == 'url_urllib' or 'url_playwright' in self.object_type:
                # Get the hash of the object.
                self._get_url_hash(check_object_index, check_object, print_kwargs=print_kwargs)

            self._set_input_file_path(check_object_index=check_object_index)

            # Check if the object was updated.
            result, message = self.diff_check_list[check_object_index].check_string(print_kwargs=print_kwargs)

            # If the object was updated, print the message in yellow color, otherwise print in green color.
            if result:
                print_api(message, color='yellow', **print_kwargs)
                # create_message_file(message, self.__class__.__name__, logger=self.logger)
            else:
                print_api(message, color='green', **print_kwargs)

            return_dict = {
                'result': result,
                'message': message,
            }

            return_list.append(return_dict)

        if self.object_type == 'dns':
            self._get_dns_list(print_kwargs=print_kwargs)

            self._set_input_file_path()

            # Check if 'known_domains' list was updated from previous cycle.
            result, message = self.diff_check_list[0].check_list_of_dicts(print_kwargs=print_kwargs)

            if result:
                # Get list of new connections only.
                new_connections_only: list = list_of_dicts.get_difference(result['old'], result['updated'])

                for connection in new_connections_only:
                    message = \
                        f"New domain: {connection['name']} | " \
                        f"{connection['domain']} | {connection['query_type']} | " \
                        f"{connection['cmdline']}"
                    # f"{connection['src_ip']}:{connection['src_port']} -> " \
                    print_api(message, color='yellow', **print_kwargs)

                    return_dict = {
                        'result': True,
                        'message': message,
                    }

                    return_list.append(return_dict)

        # Set 'first_cycle' to False, since the first cycle is finished.
        if self.first_cycle:
            self.first_cycle = False

        return return_list

    def _get_url_hash(self, check_object_index: int, check_object: str, print_kwargs: dict = None):
        """
        The function will get the hash of the URL content.

        :param check_object_index: integer, index of the object in the 'check_object_list' list.
        :param check_object: string, full URL to a web page.
        :param print_kwargs: dict, that contains all the arguments for 'print_api' function.
        """
        # Extract the method name from the object type.
        get_method = self.object_type.split('_', 1)[1]

        # If this is the first cycle, we need to set several things.
        if self.first_cycle:
            original_name: str = str()

            # If 'generate_input_file_name' is True, or 'store_original_object' is True, we need to create a
            # filename without extension.
            if self.store_original_object or self.generate_input_file_name:
                # Get the last directory from the url.
                original_name = urls.url_parser(check_object)['directories'][-1]
                # Make characters lower case.
                original_name = original_name.lower()

            # If 'store_original_object' is True, then we need to create a filepath to store.
            if self.original_object_directory:
                # Add extension to the file name.
                original_file_name = f'{original_name}.{get_method.split("_")[1]}'

                # Make path for original object.
                self.original_object_file_path = filesystem.add_object_to_path(
                    self.original_object_directory, original_file_name)

            if self.generate_input_file_name:
                # Make path for 'input_file_name'.
                self.input_file_name = f'{original_name}.txt'

            # Change settings for the DiffChecker object.
            self.diff_check_list[check_object_index].return_first_cycle = False

            self.diff_check_list[check_object_index].check_object_display_name = \
                f'{original_name}|{self.object_type}'

        # Get hash of the url. The hash will be different between direct hash of the URL content and the
        # hash of the file that was downloaded from the URL. Since the file has headers and other information
        # that is not part of the URL content. The Original downloaded file is for reference only to see
        # what was the content of the URL at the time of the download.
        hash_string = hashing.hash_url(
            check_object, get_method=get_method, path=self.original_object_file_path,
            print_kwargs=print_kwargs
        )

        # Set the hash string to the 'check_object' variable.
        self.diff_check_list[check_object_index].check_object = hash_string

    def _get_file_hash(self, check_object_index: int, check_object: str, print_kwargs: dict = None):
        """
        The function will get the hash of the URL content.

        :param check_object_index: integer, index of the object in the 'check_object_list' list.
        :param check_object: string, full URL to a web page.
        :param print_kwargs: dict, that contains all the arguments for 'print_api' function.
        """

        # If this is the first cycle, we need to set several things.
        if self.first_cycle:
            original_name: str = str()

            # If 'generate_input_file_name' is True, or 'store_original_object' is True, we need to create a
            # filename without extension.
            if self.store_original_object or self.generate_input_file_name:
                # Get the last directory from the url.
                original_name = filesystem.get_file_name(check_object)
                # Make characters lower case.
                original_name = original_name.lower()

            # If 'store_original_object' is True, then we need to create a filepath to store.
            if self.original_object_directory:
                # Add extension to the file name.
                original_file_name = original_name

                # Make path for original object.
                self.original_object_file_path = filesystem.add_object_to_path(
                    self.original_object_directory, original_file_name)

            if self.generate_input_file_name:
                # Remove dots from the file name.
                original_name_no_dots = original_name.replace('.', '-')
                # Make path for 'input_file_name'.
                self.input_file_name = f'{original_name_no_dots}.txt'

            # Change settings for the DiffChecker object.
            self.diff_check_list[check_object_index].return_first_cycle = False

            self.diff_check_list[check_object_index].check_object_display_name = \
                f'{original_name}|{self.object_type}'

        # Copy the file to the original object directory.
        if self.original_object_file_path:
            filesystem.copy_file(check_object, self.original_object_file_path)

        # Get hash of the file.
        hash_string = hashing.hash_file(check_object)

        # Set the hash string to the 'check_object' variable.
        self.diff_check_list[check_object_index].check_object = hash_string

    def _get_dns_list(self, print_kwargs: dict = None):
        """
        The function will get the list of DNS events and return only the new ones.

        :param print_kwargs: dict, that contains all the arguments for 'print_api' function.

        :return: list of dicts, of new DNS events.
        """

        if self.first_cycle:
            original_name: str = str()

            # Initialize objects for DNS monitoring.
            self.fetch_engine = DnsTrace(enable_process_poller=True, attrs=['name', 'cmdline', 'domain', 'query_type'])

            # Start DNS monitoring.
            self.fetch_engine.start()

            # Change settings for the DiffChecker object.
            self.diff_check_list[0].return_first_cycle = True

            if self.generate_input_file_name:
                original_name = 'known_domains'
                # Make path for 'input_file_name'.
                self.input_file_name = f'{original_name}.txt'

            self.diff_check_list[0].check_object_display_name = \
                f'{original_name}|{self.object_type}'

            # Set the 'check_object' to empty list, since we will append the list of DNS events.
            self.diff_check_list[0].check_object = list()

        # 'emit()' method is blocking (it uses 'get' of queue instance)
        # will return a dict with current DNS trace event.
        event_dict = self.fetch_engine.emit()

        if event_dict not in self.diff_check_list[0].check_object:
            self.diff_check_list[0].check_object.append(event_dict)

        # Sort list of dicts by process name and then by process cmdline.
        self.diff_check_list[0].check_object = list_of_dicts.sort_by_keys(
            self.diff_check_list[0].check_object, ['cmdline', 'name'], case_insensitive=True)

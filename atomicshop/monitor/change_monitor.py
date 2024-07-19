from typing import Literal, Union

from .checks import dns, network, file, url, process_running


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
            object_type_settings: dict = None,
            etw_session_name: str = None,
            etw_process_session_name: str = None
    ):
        """
        :param object_type: string, type of object to check. The type must be one of the following:
            'file': 'check_object' must contain string of full path to the file.
            'dns': 'check_object' will be none, since the DNS events will be queried from the system.
            'network': 'check_object' will be none, since the network events will be queried from the system.
            'process_running': 'check_object' must contain list of strings of process names to check if they are
                running.
                Example: ['chrome.exe', 'firefox.exe']
                No file is written.
            'url_*': 'check_object' must contain string of full URL to a web page to download.
                'url_urllib': download using 'urllib' library to HTML file.
                'url_playwright_html': download using 'playwright' library to HTML file.
                'url_playwright_pdf': download using 'playwright' library to PDF file.
                'url_playwright_png': download using 'playwright' library to PNG file.
                'url_playwright_jpeg': download using 'playwright' library to JPEG file.
        :param object_type_settings: dict, specific settings for the object type.
            'dns': Check the default settings example in 'DNS__DEFAULT_SETTINGS'.
            'file': Check the default settings example in 'FILE__URL__DEFAULT_SETTINGS'.
            'url_*': Check the default settings example in 'FILE__URL__DEFAULT_SETTINGS'.
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
        :param etw_session_name: string, the name of the ETW session. This should help you manage your ETW sessions
            with logman and other tools: logman query -ets
            If not provided, a default name will be generated.
            'dns': 'AtomicShopDnsTrace'
        :param etw_process_session_name: string, the name of the ETW session for tracing process creation.
            This is needed to correlate the process cmd with the DNS requests PIDs.

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
        self.etw_session_name: str = etw_session_name
        self.etw_process_session_name: str = etw_process_session_name

        # === Additional variables ========================================

        self.checks_instance = None
        self._setup_check()

    def _setup_check(self):
        if self.object_type == 'file':
            if not self.object_type_settings:
                self.object_type_settings = FILE__URL__DEFAULT_SETTINGS

            self.checks_instance = file.FileCheck(self)
        elif self.object_type.startswith('url_'):
            if not self.object_type_settings:
                self.object_type_settings = FILE__URL__DEFAULT_SETTINGS

            self.checks_instance = url.UrlCheck(self)
        elif self.object_type == 'dns':
            if not self.object_type_settings:
                self.object_type_settings = DNS__DEFAULT_SETTINGS

            self.checks_instance = dns.DnsCheck(self)
        elif self.object_type == 'network':
            self.checks_instance = network.NetworkCheck(self)
        elif self.object_type == 'process_running':
            self.checks_instance = process_running.ProcessRunningCheck(self)
        else:
            raise ValueError(f"ERROR: Unknown object type: {self.object_type}")

    def check_cycle(self, print_kwargs: dict = None):
        """
        Checks if file was updated.
        :param print_kwargs: dict, that contains all the arguments for 'print_api' function.
        :return: None
        """

        return_list = self.checks_instance.execute_cycle(print_kwargs=print_kwargs)

        return return_list

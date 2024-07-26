import os
import sys
from pathlib import Path

from .. import filesystem
from ..file_io import tomls
from ..basics.classes import import_first_class_name_from_file_path
from ..wrappers.loggingw import loggingw
from .engines.__reference_general import parser___reference_general, responder___reference_general, \
    recorder___reference_general


class ModuleCategory:
    def __init__(self, script_directory: str):
        self.domain_list: list = list()
        self.engine_name: str = str()
        self.script_directory: str = script_directory

        self.parser_file_path: str = str()
        self.responder_file_path: str = str()
        self.recorder_file_path: str = str()

        self.parser_class_object: str = str()
        self.responder_class_object: str = str()
        self.recorder_class_object: str = str()

        # The instance of the recorder class that will be initiated once in the script start
        self.responder_instance = None

    def fill_engine_fields_from_general_reference(self, engines_fullpath: str):
        # Reference module variables.
        self.engine_name = '__reference_general'
        reference_folder_path: str = engines_fullpath + os.sep + self.engine_name
        # Full path to file.
        self.parser_file_path = reference_folder_path + os.sep + "parser___reference_general.py"
        self.responder_file_path = reference_folder_path + os.sep + "responder___reference_general.py"
        self.recorder_file_path = reference_folder_path + os.sep + "recorder___reference_general.py"

    def fill_engine_fields_from_config(self, engine_config_file_path: str):
        # Read the configuration file of the engine.
        configuration_data = tomls.read_toml_file(engine_config_file_path)

        engine_directory_path: str = str(Path(engine_config_file_path).parent)
        self.engine_name = Path(engine_directory_path).name

        # Getting the parameters from engine config file
        self.domain_list = configuration_data['domains']

        # If there's module configuration file, but no domains in it, there's no point to continue.
        # Since, each engine is based on domains.
        if not self.domain_list or self.domain_list[0] == '':
            raise ValueError(f"Engine Configuration file doesn't contain any domains: {engine_config_file_path}")

        # Full path to file
        self.parser_file_path = filesystem.get_file_paths_from_directory(
            engine_directory_path, file_name_check_pattern=configuration_data['parser_file'])[0]
        self.responder_file_path = filesystem.get_file_paths_from_directory(
            engine_directory_path, file_name_check_pattern=configuration_data['responder_file'])[0]
        self.recorder_file_path = filesystem.get_file_paths_from_directory(
            engine_directory_path, file_name_check_pattern=configuration_data['recorder_file'])[0]

    def initialize_engine(self, logs_path: str, logger=None, reference_general: bool = False, **kwargs):
        if not reference_general:
            self.parser_class_object = import_first_class_name_from_file_path(
                self.script_directory, self.parser_file_path, logger=logger, stdout=False)
            self.responder_class_object = import_first_class_name_from_file_path(
                self.script_directory, self.responder_file_path, logger=logger, stdout=False)
            self.recorder_class_object = import_first_class_name_from_file_path(
                self.script_directory, self.recorder_file_path, logger=logger, stdout=False)
        else:
            self.parser_class_object = parser___reference_general.ParserGeneral
            self.responder_class_object = responder___reference_general.ResponderGeneral
            self.recorder_class_object = recorder___reference_general.RecorderGeneral

        try:
            # Since we're using responder to aggregate requests to build responses based on several
            # requests, we need to initiate responder's class only once in the beginning and assign
            # this instance to a variable that will be called later per domain.
            self.responder_instance = self.responder_class_object()
        except Exception as exception_object:
            logger.error_exception(f"Exception while initializing responder: {exception_object}")
            sys.exit()

        # Initiating logger for each engine by its name
        # initiate_logger(current_module.engine_name, log_file_extension)
        loggingw.get_complex_logger(
            logger_name=self.engine_name,
            directory_path=logs_path,
            add_stream=True,
            add_timedfile=True,
            formatter_streamhandler='DEFAULT',
            formatter_filehandler='DEFAULT'
        )


# Assigning external class object by message domain received from client. If the domain is not in the list,
# the reference general module will be assigned.
def assign_class_by_domain(
        engines_list: list, message_domain_name: str, reference_module, config, logger=None):
    # Defining return variables:
    function_parser = None
    function_responder = None
    function_recorder = None

    # In case SNI came empty in the request from client, then there's no point in iterating through engine domains.
    if message_domain_name:
        # If the engines_usage is set to True in the config file, then we'll iterate through the list of engines
        # to find the domain in the list of domains of the engine.
        if config['tcp']['engines_usage']:
            # Checking if current domain is in engines' domain list to activate domain specific engine
            for function_module in engines_list:
                # The list: matches_list = ["domain1.com", "domain2.com", "domain3.com"]
                # The string: a_string = "www.domain1.com"
                # Checking that the message subdomain + domain contains current module's domain name
                # Template Should be like this: if any(x in a_string for x in matches_list):

                # On the other hand if you want to find if partial string is
                # in the list of strings: if any(a_string in x for x in matches_list):
                # In this case list is the same and string: a_string = domain
                if any(x in message_domain_name for x in function_module.domain_list):
                    # Assigning modules by current engine of the domain
                    function_parser = function_module.parser_class_object
                    function_recorder = function_module.recorder_class_object
                    # Since the responder is being initiated only once, we're assigning only the instance
                    function_responder = function_module.responder_instance

                    logger.info(f"Assigned Modules for [{message_domain_name}]: "
                                f"{function_module.parser_class_object.__name__}, "
                                f"{function_module.responder_class_object.__name__}, "
                                f"{function_module.recorder_class_object.__name__}")

                    # If the domain was found in the current list of class domains, we can stop the loop
                    break

    # If none of the domains were found in the engine domains list, then we'll assign reference module.
    # It's enough to check only parser, since responder and recorder also will be empty.
    # This section is also relevant if SNI came empty in the request from the client and no domain was passed by the
    # DNS Server.
    if not function_parser:
        # Assigning modules by current engine of the domain
        function_parser = reference_module.parser_class_object
        function_recorder = reference_module.recorder_class_object
        # Since the responder is being initiated only once, we're assigning only the instance
        function_responder = reference_module.responder_instance

    # Return all the initiated modules
    return function_parser, function_responder, function_recorder

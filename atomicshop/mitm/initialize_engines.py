import os
from pathlib import Path

from ..file_io import tomls
from ..basics.classes import import_first_class_name_from_file_path
from .engines.__reference_general import parser___reference_general, requester___reference_general, \
    responder___reference_general, recorder___reference_general


class ModuleCategory:
    def __init__(self, script_directory: str):
        self.engine_name: str = str()
        self.script_directory: str = script_directory

        self.domain_list: list = list()
        self.domain_target_dict: dict = dict()
        self.is_localhost: bool = bool()
        self.mtls: dict = dict()

        self.parser_file_path: str = str()
        self.requester_file_path: str = str()
        self.responder_file_path: str = str()
        self.recorder_file_path: str = str()

        self.parser_class_object: str = str()
        self.requester_class_object: str = str()
        self.responder_class_object: str = str()
        self.recorder_class_object: str = str()

    def fill_engine_fields_from_general_reference(self, engines_fullpath: str):
        # Reference module variables.
        self.engine_name = '__reference_general'
        reference_folder_path: str = engines_fullpath + os.sep + self.engine_name
        # Full path to file.
        self.parser_file_path = reference_folder_path + os.sep + "parser___reference_general.py"
        self.requester_file_path = reference_folder_path + os.sep + "requester___reference_general.py"
        self.responder_file_path = reference_folder_path + os.sep + "responder___reference_general.py"
        self.recorder_file_path = reference_folder_path + os.sep + "recorder___reference_general.py"

    def fill_engine_fields_from_config(self, engine_config_file_path: str):
        # Read the configuration file of the engine.
        configuration_data = tomls.read_toml_file(engine_config_file_path)

        engine_directory_path: str = str(Path(engine_config_file_path).parent)
        self.engine_name = Path(engine_directory_path).name

        # Getting the parameters from engine config file
        self.domain_list = configuration_data['engine']['domains']
        self.is_localhost = bool(configuration_data['engine']['localhost'])

        if 'mtls' in configuration_data:
            self.mtls = configuration_data['mtls']

        # If there's module configuration file, but no domains in it, there's no point to continue.
        # Since, each engine is based on domains.
        if not self.domain_list or self.domain_list[0] == '':
            raise ValueError(f"Engine Configuration file doesn't contain any domains: {engine_config_file_path}")

        # This is needed for backwards compatibility before glass 1.8.2, atomicshop 2.20.6
        # When the name of each file was following the pattern: parser_<EngineName>.py, responder_<EngineName>.py, recorder_<EngineName>.py
        if os.path.isfile(f"{engine_directory_path}{os.sep}parser.py"):
            file_name_suffix: str = ''
        else:
            file_name_suffix: str = f"_{self.engine_name}"

        # Full path to file
        self.parser_file_path = f"{engine_directory_path}{os.sep}parser{file_name_suffix}.py"
        self.requester_file_path = f"{engine_directory_path}{os.sep}requester{file_name_suffix}.py"
        self.responder_file_path = f"{engine_directory_path}{os.sep}responder{file_name_suffix}.py"
        self.recorder_file_path = f"{engine_directory_path}{os.sep}recorder{file_name_suffix}.py"

        for domain_index, domain_port_string in enumerate(self.domain_list):
            # Splitting the domain and port
            domain, port = domain_port_string.split(':')

            self.domain_target_dict[domain] = {'ip': None, 'port': port}

        for subdomain, file_name in self.mtls.items():
            self.mtls[subdomain] = f'{engine_directory_path}{os.sep}{file_name}'

    def initialize_engine(self, reference_general: bool = False) -> tuple[int, str]:
        try:
            if not reference_general:
                self.parser_class_object = import_first_class_name_from_file_path(
                    self.script_directory, self.parser_file_path)
                self.requester_class_object = import_first_class_name_from_file_path(
                    self.script_directory, self.requester_file_path)
                self.responder_class_object = import_first_class_name_from_file_path(
                    self.script_directory, self.responder_file_path)
                self.recorder_class_object = import_first_class_name_from_file_path(
                    self.script_directory, self.recorder_file_path)
            else:
                self.parser_class_object = parser___reference_general.ParserGeneral
                self.requester_class_object = requester___reference_general.RequesterGeneral
                self.responder_class_object = responder___reference_general.ResponderGeneral
                self.recorder_class_object = recorder___reference_general.RecorderGeneral
        except ModuleNotFoundError as e:
            return 1, str(e)

        return 0, ''


def assign_class_by_domain(
        engines_list: list,
        message_domain_name: str,
        reference_module
):
    """
    Assigning external class object by message domain received from client. If the domain is not in the list,
    the reference general module will be assigned.
    """

    # In case SNI came empty in the request from client, then there's no point in iterating through engine domains.
    module = None
    if message_domain_name:
        # If engine/s exit, the engines_list will not be empty, then we'll iterate through the list of engines
        # to find the domain in the list of domains of the engine.
        if engines_list:
            # Checking if current domain is in engines' domain list to activate domain specific engine
            for function_module in engines_list:
                # The list: matches_list = ["domain1.com", "domain2.com", "domain3.com"]
                # The string: a_string = "www.domain1.com"
                # Checking that the message subdomain + domain contains current module's domain name
                # Template Should be like this: if any(x in a_string for x in matches_list):

                # On the other hand if you want to find if partial string is
                # in the list of strings: if any(a_string in x for x in matches_list):
                # In this case list is the same and string: a_string = domain
                if any(x in message_domain_name for x in function_module.domain_target_dict.keys()):
                    # Assigning module by current engine of the domain
                    module = function_module

                    # If the domain was found in the current list of class domains, we can stop the loop
                    break

    # If none of the domains were found in the engine domains list, then we'll assign reference module.
    # It's enough to check only parser, since responder and recorder also will be empty.
    # This section is also relevant if SNI came empty in the request from the client and no domain was passed by the
    # DNS Server.
    if not module:
        module = reference_module

    return module

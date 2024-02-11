import os
from pathlib import Path

from ... import filesystem
from ...basics import strings


GENERAL_CLASS_NAME: str = "General"
REFERENCE_ENGINE_NAME: str = "__reference_general"

ENGINES_DIRECTORY_NAME: str = 'engines'
CONFIG_FILE_NAME: str = "engine_config.toml"

PARSER_FILE_NAME: str = f"parser_{REFERENCE_ENGINE_NAME}.py"
RESPONDER_FILE_NAME: str = f"responder_{REFERENCE_ENGINE_NAME}.py"
RECORDER_FILE_NAME: str = f"recorder_{REFERENCE_ENGINE_NAME}.py"

SCRIPT_DIRECTORY: str = filesystem.get_file_directory(__file__)
ENGINES_DIRECTORY_PATH: str = filesystem.get_working_directory() + os.sep + ENGINES_DIRECTORY_NAME


class CreateModuleTemplate:
    def __init__(self, engine_name: str, domains: list):
        # === Get input variables. ===
        self.engine_name: str = engine_name
        self.domains: list = domains

        # New engine's directory.
        self.new_engine_directory: str = ENGINES_DIRECTORY_PATH + os.sep + self.engine_name
        # Replace all the spaces in 'engine_name' with underscore '_'. If there are no spaces - nothing is done.
        self.engine_name = self.engine_name.replace(" ", "_")
        # Create the class name from the engine name.
        self.engine_class_name: str = strings.capitalize_first_letter(self.engine_name)

        # === General modules paths. ===
        reference_folder_path: str = SCRIPT_DIRECTORY + os.sep + REFERENCE_ENGINE_NAME
        self.parser_general_path: str = reference_folder_path + os.sep + PARSER_FILE_NAME
        self.responder_general_path: str = reference_folder_path + os.sep + RESPONDER_FILE_NAME
        self.recorder_general_path: str = reference_folder_path + os.sep + RECORDER_FILE_NAME

        self.create_template()

    def create_template(self):
        print(f"Engine Name: {self.engine_name}")
        print(f"Engine Class Name: {self.engine_class_name}")

        # Create the 'engines' directory if it doesn't exist.
        filesystem.create_directory(ENGINES_DIRECTORY_PATH)

        # Create new engines folder.
        filesystem.create_directory(self.new_engine_directory)

        module_files_list: list = [self.parser_general_path, self.responder_general_path, self.recorder_general_path]
        for file_path in module_files_list:
            file_name = Path(file_path).name
            module_prefix = file_name.rsplit('_')[0]

            new_engine_module_file_name, new_engine_module_file_path = \
                self.create_engine_module_from_reference(module_prefix, file_path)
            print(f"Converted: {file_path}")
            print(f"To: {new_engine_module_file_path}")

        self.create_config_file()

    def create_engine_module_from_reference(self, prefix: str, file_full_path: str):
        # Defining variables.
        new_module_file_name: str = str()
        new_module_full_path: str = str()

        # Reading the module file to string.
        with open(file_full_path, 'r') as input_file:
            file_content_string = input_file.read()

        if GENERAL_CLASS_NAME in file_content_string:
            new_content_string = file_content_string.replace(GENERAL_CLASS_NAME, self.engine_class_name)

            new_module_file_name = prefix + "_" + self.engine_name + '.py'

            new_module_full_path = self.new_engine_directory + os.sep + new_module_file_name

            with open(new_module_full_path, 'w') as output_file:
                output_file.write(new_content_string)

        return new_module_file_name, new_module_full_path

    def create_config_file(self):
        # Defining variables.
        config_lines_list: list = list()

        # Add "" to each domain.
        domains_with_quotes: list = [f'"{domain}"' for domain in self.domains]
        config_lines_list.append(f'domains = [{", ".join(domains_with_quotes)}]')

        config_file_path = self.new_engine_directory + os.sep + CONFIG_FILE_NAME

        with open(config_file_path, 'w') as output_file:
            output_file.write('\n'.join(config_lines_list))

        print(f"Config File Created: {config_file_path}")

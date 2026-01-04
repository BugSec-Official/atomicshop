import sys
import os
import argparse
from typing import Literal

from ... import filesystem, consoles
from ...basics import strings
from rich.console import Console


console = Console()


GENERAL_CLASS_NAME: str = "General"
REFERENCE_ENGINE_NAME: str = "__reference_general"

ENGINES_DIRECTORY_NAME: str = 'engines'
CONFIG_FILE_NAME: str = "engine_config.toml"

REFERENCE_PARSER_FILE_NAME: str = f"parser_{REFERENCE_ENGINE_NAME}.py"
REFERENCE_RESPONDER_FILE_NAME: str = f"responder_{REFERENCE_ENGINE_NAME}.py"
REFERENCE_REQUESTER_FILE_NAME: str = f"requester_{REFERENCE_ENGINE_NAME}.py"
REFERENCE_RECORDER_FILE_NAME: str = f"recorder_{REFERENCE_ENGINE_NAME}.py"

SCRIPT_DIRECTORY: str = filesystem.get_file_directory(__file__)
ENGINES_DIRECTORY_PATH: str = filesystem.get_working_directory() + os.sep + ENGINES_DIRECTORY_NAME


class CreateModuleTemplate:
    def __init__(
            self,
            engine_name: str = None
    ):
        # === Get input variables. ===
        self.engine_name: str = engine_name
        self.domains: list = ['example.com:443', 'example.org:80']

        # New engine's directory.
        self.new_engine_directory: str = ENGINES_DIRECTORY_PATH + os.sep + self.engine_name
        # Replace all the spaces in 'engine_name' with underscore '_'. If there are no spaces - nothing is done.
        self.engine_name = self.engine_name.replace(" ", "_")
        # Create the class name from the engine name.
        self.engine_class_name: str = strings.capitalize_first_letter(self.engine_name)

        # === General modules paths. ===
        reference_folder_path: str = SCRIPT_DIRECTORY + os.sep + REFERENCE_ENGINE_NAME
        self.parser_general_path: str = reference_folder_path + os.sep + REFERENCE_PARSER_FILE_NAME
        self.responder_general_path: str = reference_folder_path + os.sep + REFERENCE_RESPONDER_FILE_NAME
        self.requester_general_path: str = reference_folder_path + os.sep + REFERENCE_REQUESTER_FILE_NAME
        self.recorder_general_path: str = reference_folder_path + os.sep + REFERENCE_RECORDER_FILE_NAME

        self.parser_file_name: str = f"parser.py"
        self.responder_file_name: str = f"responder.py"
        self.requester_file_name: str = f"requester.py"
        self.recorder_file_name: str = f"recorder.py"

        self.create_template()

    def create_template(self):
        print(f"Engine Name: {self.engine_name}")
        print(f"Engine Class Name: {self.engine_class_name}")

        # Create the 'engines' directory if it doesn't exist.
        filesystem.create_directory(ENGINES_DIRECTORY_PATH)

        # Create new engines' folder.
        filesystem.create_directory(self.new_engine_directory)

        self._create_engine_module_from_reference(file_path=self.parser_general_path, module_type='parser')
        self._create_engine_module_from_reference(file_path=self.responder_general_path, module_type='responder')
        self._create_engine_module_from_reference(file_path=self.requester_general_path, module_type='requester')
        self._create_engine_module_from_reference(file_path=self.recorder_general_path, module_type='recorder')

        self.create_config_file()

        consoles.wait_any_key()

    def create_config_file(self):
        # Defining variables.
        config_lines_list: list = list()

        # Add "" to each domain.
        domains_with_quotes: list = [f'"{domain}"' for domain in self.domains]

        config_lines_list.append('[engine]')
        config_lines_list.append(f'domains = [{", ".join(domains_with_quotes)}]\n')
        config_lines_list.append('[on_port_connect]')
        config_lines_list.append('#5000 = "31.31.31.31:443"')
        config_lines_list.append('#5000 = "ip_port_address.txt"\n')
        config_lines_list.append('[mtls]')
        config_lines_list.append('# "subdomain.domain.com" = "file_name_in_current_dir.pem"\n')
        # config_lines_list.append(f'\n')

        config_file_path = self.new_engine_directory + os.sep + CONFIG_FILE_NAME

        with open(config_file_path, 'w') as output_file:
            output_file.write('\n'.join(config_lines_list))

        console.print(f"Config File Created: {config_file_path}", style="bright_blue")

    def _create_engine_module_from_reference(
            self,
            file_path: str,
            module_type: Literal['parser', 'responder', 'requester', 'recorder']
    ):

        if module_type == 'parser':
            new_module_file_name = self.parser_file_name
        elif module_type == 'responder':
            new_module_file_name = self.responder_file_name
        elif module_type == 'requester':
            new_module_file_name = self.requester_file_name
        elif module_type == 'recorder':
            new_module_file_name = self.recorder_file_name
        else:
            raise ValueError(f"Module type is not recognized: {module_type}")

        # Reading the module file to string.
        with open(file_path, 'r', encoding='utf-8') as input_file:
            file_content_string = input_file.read()

        new_module_full_path: str = str()
        if GENERAL_CLASS_NAME in file_content_string:
            new_content_string = file_content_string.replace(GENERAL_CLASS_NAME, self.engine_class_name)

            new_module_full_path = self.new_engine_directory + os.sep + new_module_file_name

            with open(new_module_full_path, 'w') as output_file:
                output_file.write(new_content_string)

        print(f"Converted: {file_path}")
        console.print(f"To: {new_module_full_path}", style="green")


def create_template(engine_name: str) -> int:
    CreateModuleTemplate(engine_name=engine_name)
    return 0


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Create a new engine module template.')
    parser.add_argument('engine_name', type=str, help='The name of the new engine.')
    return parser


def main() -> int:
    arg_parser: argparse.ArgumentParser = _make_parser()
    args = arg_parser.parse_args()

    return create_template(**vars(args))


if __name__ == '__main__':
    sys.exit(main())
import os
from ... import filesystem


class CreateModuleTemplate:
    def __init__(self, engine_name: str, domains: list, engines_directory_path: str):
        # === Get input variables. ===
        self.engine_name: str = engine_name
        self.domains: list = domains
        self.engines_directory_path: str = engines_directory_path

        # === Working directory of current script. ===
        # 'filesystem.get_working_directory()' won't work here because the function is called from another script.
        self.working_directory: str = filesystem.get_file_directory(__file__)

        # === Variable manipulations ===
        # New engines directory.
        self.new_engine_directory: str = self.engines_directory_path + os.sep + self.engine_name
        # Replace all the spaces in 'engine_name' with underscore '_'. If there are no spaces - nothing is done.
        self.engine_name = self.engine_name.replace(" ", "_")
        # Take the first letter of the name 'engine_name[0]' (0 is the first letter of the 'engine_name' string) and
        # capitalize it '.upper()' and add the rest of the letters
        # as is with 'engine_name[1:]' (1 is the second letter of
        # the string 'engine_name' and ':' means the rest of the string.
        self.engine_class_name: str = self.engine_name[0].upper() + self.engine_name[1:]

        # === General modules paths. ===
        reference_folder_path: str = self.working_directory + os.sep + '__reference_general'
        self.parser_general_path: str = reference_folder_path + os.sep + 'parser___reference_general.py'
        self.responder_general_path: str = reference_folder_path + os.sep + 'responder___reference_general.py'
        self.recorder_general_path: str = reference_folder_path + os.sep + 'recorder___reference_general.py'

        # Modules file name prefixes.
        self.general_class_name_string: str = "General"

        # Configuration file name that will be created with new settings.
        self.engines_folder_name: str = 'engines'
        self.config_file_name: str = "engine_config.ini"

        # Module file list in the folder.
        self.new_module_dict: dict = dict()

        self.create_template()

    def create_template(self):
        print(f"Engine Name: {self.engine_name}")
        print(f"Engine Class Name: {self.engine_class_name}")

        # Create new engines folder.
        filesystem.create_folder(self.new_engine_directory)

        module_files_list: list = [self.parser_general_path, self.responder_general_path, self.recorder_general_path]
        for file_path in module_files_list:
            file_name = file_path.rsplit(os.sep, maxsplit=1)[1]
            module_prefix = file_name.rsplit('_')[0]

            new_engine_module_file_name, new_engine_module_file_path = \
                self.create_engine_module_from_reference(module_prefix, file_path)
            print(f"Converted: {file_path}")
            print(f"To: {new_engine_module_file_path}")
            self.new_module_dict.update({module_prefix: new_engine_module_file_name})

        self.create_config_file()

    def create_engine_module_from_reference(self, prefix: str, file_full_path: str):
        # Defining variables.
        new_module_file_name: str = str()
        new_module_full_path: str = str()

        # Reading the module file to string.
        with open(file_full_path, 'r') as input_file:
            file_content_string = input_file.read()

        if self.general_class_name_string in file_content_string:
            new_content_string = file_content_string.replace(self.general_class_name_string, self.engine_class_name)

            new_module_file_name = prefix + "_" + self.engine_name + '.py'

            new_module_full_path = self.new_engine_directory + os.sep + new_module_file_name

            with open(new_module_full_path, 'w') as output_file:
                output_file.write(new_content_string)

        return new_module_file_name, new_module_full_path

    def create_config_file(self):
        # Defining variables.
        config_lines_list: list = list()

        config_lines_list.append("[engine]")
        config_lines_list.append("domains = " + ', '.join(self.domains))

        for key, value in self.new_module_dict.items():
            config_lines_list.append(
                f"{key}_path = {self.engines_folder_name}{os.sep}{self.engine_name}{os.sep}{value}")

        config_file_path = self.new_engine_directory + os.sep + self.config_file_name

        with open(config_file_path, 'w') as output_file:
            output_file.write('\n'.join(config_lines_list))

        print(f"Config File Created: {config_file_path}")

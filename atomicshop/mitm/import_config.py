import sys

from ..wrappers.configparserw import ConfigParserWrapper
from ..filesystem import check_file_existence
from ..permissions import is_admin
from ..basics.booleans import check_3_booleans_when_only_1_can_be_true


class ImportConfig:
    """
    ImportConfig class is responsible for importing 'config.ini' file and its variables.
    """

    def __init__(self, file_name: str, directory_path: str):
        self.directory_path: str = directory_path
        self.admin_rights = None
        self.config_parser = ConfigParserWrapper(file_name=file_name, directory_path=self.directory_path)
        self.config: dict = dict()

    def open(self) -> None:
        """
        Open configuration file

        :return:
        """

        # Read file to dictionary.
        self.config_parser.read_to_dict()

        # === Convert string values to python objects. ===
        # Auto convert to booleans.
        self.config_parser.auto_convert_values(integers=False)
        # Convert keys.
        self.config_parser.convert_string_values(['listening_port', 'cache_timeout_minutes'], 'int')
        self.config_parser.convert_string_values(
            ['forwarding_dns_service_ipv4_list___only_for_localhost'], 'list')
        self.config_parser.convert_string_values(['listening_port_list'], 'list_of_int')
        self.config_parser.convert_string_values(
            ['logs_path', 'recordings_path', 'custom_server_certificate_path', 'custom_private_key_path',
             'sni_server_certificates_cache_directory',
             'sni_server_certificate_from_server_socket_download_directory'],
            'path_relative_to_full')

        # Move final dict to local config.
        self.config = self.config_parser.config

        self.check_configurations()
        self.manipulations_after_import()

    def check_configurations(self):
        # Check if both DNS and TCP servers are disabled. ==============================================================
        if not self.config['dns']['enable_dns_server'] and not self.config['tcp']['enable_tcp_server']:
            print("What are you trying to do? You had disabled both DNS and TCP servers in config ini file.\n"
                  "Exiting...")
            sys.exit()

        # Check [tcp_server] boolean configurations. ===================================================================
        if not self.config['tcp']['engines_usage'] and self.config['tcp']['server_response_mode']:
            print(
                "You can't set [server_response_mode = True], while setting\n"
                "[engines_usage = False].\n"
                "No engine modules will be loaded - so nothing to respond to.\n"
                "Exiting..."
            )

        check_3_booleans_when_only_1_can_be_true(
            (self.config['certificates']['default_server_certificate_usage'], 'default_server_certificate_usage'),
            (self.config['certificates']['sni_create_server_certificate_for_each_domain'],
             'sni_create_server_certificate_for_each_domain'),
            (self.config['certificates']['custom_server_certificate_usage'], 'custom_server_certificate_usage'))

        if not self.config['certificates']['default_server_certificate_usage'] and \
                self.config['certificates']['sni_default_server_certificate_addons']:
            print(
                f"No point setting [default_server_certificate_addons = True]\n"
                f"If you're not going to use default certificates [default_server_certificate_usage = False]\n"
                f"Exiting...")
            sys.exit()

        if self.config['certificates']['sni_get_server_certificate_from_server_socket'] and \
                not self.config['certificates']['sni_create_server_certificate_for_each_domain']:
            print("[sni_get_server_certificate_from_server_socket] was set to 'True', "
                  "but no [sni_create_server_certificate_for_each_domain] was specified.\n"
                  "Exiting...")
            sys.exit()

        if self.config['certificates']['custom_server_certificate_usage'] and \
                not self.config['certificates']['custom_server_certificate_path']:
            print("[custom_server_certificate_usage] was set to 'True', but no [custom_server_certificate_path] "
                  "was specified.\n"
                  "Exiting...")
            sys.exit()

        # Check admin right if on localhost ============================================================================
        # If the 'config.dns['target_tcp_server_ipv4']' IP address is localhost, then we need to check if the script
        # is executed with admin rights. There are some processes that 'psutil' can't get their command line if not
        # executed with administrative privileges.
        # Also, check Admin privileges only if 'config.tcp['get_process_name']' was set to 'True' in 'config.ini' of
        # the script.
        if self.config['dns']['target_tcp_server_ipv4'] == "127.0.0.1" and self.config['ssh']['get_process_name']:
            self.admin_rights = is_admin()

            # If we're not running with admin rights, prompt to the user and make him decide what to do.
            # If he wants to continue running with 'psutil' exceptions or close the script and rerun with admin rights.
            if not self.admin_rights:
                print("=============================================================")
                error_on_admin: str = \
                    "[!!!] You're running the script in LOCALHOST mode without Administrative Privileges.\n" \
                    "[!!!] 'psutil' needs them to read Command Lines of system Processes.\n" \
                    "[!!!] Press [ENTER] to CONTINUE running with errors " \
                    "on Process Command Line harvesting or rerun the script with Administrative Rights..."
                print(error_on_admin)
                # Stopping execution and waiting for user's [ENTER] key.
                input()
                print("=============================================================")

    def manipulations_after_import(self):
        # If 'custom_certificate_usage' was set to 'True'.
        if self.config['certificates']['custom_server_certificate_usage']:
            # Check file existence.
            if not check_file_existence(file_path=self.config['certificates']['custom_server_certificate_path']):
                raise FileNotFoundError

            # And if 'custom_private_key_path' field was populated in [advanced] section, we'll check its existence.
            if self.config['certificates']['custom_private_key_path']:
                # Check private key file existence.
                if not check_file_existence(file_path=self.config['certificates']['custom_private_key_path']):
                    raise FileNotFoundError

        skip_extensions: list = list()
        if self.config['skip_extensions']['tls_web_client_authentication']:
            skip_extensions.append('1.3.6.1.5.5.7.3.2')
        if self.config['skip_extensions']['crl_distribution_points']:
            skip_extensions.append('2.5.29.31')
        if self.config['skip_extensions']['authority_information_access']:
            skip_extensions.append('1.3.6.1.5.5.7.1.1')

        self.config['skip_extensions'] = skip_extensions

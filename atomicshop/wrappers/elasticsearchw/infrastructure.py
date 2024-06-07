import sys
import time
import requests

from ...print_api import print_api
from ... import filesystem
from .. import ubuntu_terminal
from . import config_basic


def is_elastic_service_running():
    return ubuntu_terminal.is_service_running(config_basic.UBUNTU_ELASTIC_SERVICE_NAME, return_false_on_error=False)


def enable_elastic_service():
    ubuntu_terminal.enable_service(config_basic.UBUNTU_ELASTIC_SERVICE_NAME, sudo=True)


def start_elastic_service():
    ubuntu_terminal.start_service(config_basic.UBUNTU_ELASTIC_SERVICE_NAME, sudo=True)


def is_kibana_service_running():
    return ubuntu_terminal.is_service_running(config_basic.UBUNTU_KIBANA_SERVICE_NAME, return_false_on_error=False)


def enable_kibana_service():
    ubuntu_terminal.enable_service(config_basic.UBUNTU_KIBANA_SERVICE_NAME, sudo=True)


def start_kibana_service():
    ubuntu_terminal.start_service(config_basic.UBUNTU_KIBANA_SERVICE_NAME, sudo=True)


def start_elastic_and_check_service_availability(wait_time_seconds: float = 30, exit_on_error: bool = True):
    """
    Function starts the Elasticsearch service and checks its availability.
    :param wait_time_seconds: float, the time to wait after starting the service before checking
        the service availability.
    :param exit_on_error: bool, if True, the function will exit the program if the service is not available.
    :return:
    """

    # Start, enable and check the Elasticsearch service.
    ubuntu_terminal.start_enable_service_check_availability(
        service_name=config_basic.UBUNTU_ELASTIC_SERVICE_NAME,
        wait_time_seconds=wait_time_seconds,
        exit_on_error=exit_on_error
    )

    # Check if Elasticsearch is running.
    if not is_server_available():
        if exit_on_error:
            sys.exit(1)


def start_kibana_and_check_service_availability(wait_time_seconds: float = 30, exit_on_error: bool = True):
    """
    Function starts the Kibana service and checks its availability.
    :param wait_time_seconds: float, the time to wait after starting the service before checking
        the service availability.
    :param exit_on_error: bool, if True, the function will exit the program if the service is not available.
    :return:
    """

    # Start, enable and check the Elasticsearch service.
    ubuntu_terminal.start_enable_service_check_availability(
        service_name=config_basic.UBUNTU_KIBANA_SERVICE_NAME,
        wait_time_seconds=wait_time_seconds,
        exit_on_error=exit_on_error
    )


def is_elastic_config_file_exists(
        config_file_path: str = None,
        exit_on_error: bool = False,
        output_message: bool = False
) -> bool:
    """
    The function checks if the Elasticsearch configuration file exists.

    :param config_file_path: str, the path to the configuration file.
    :param exit_on_error: bool, if True, the function will exit the program if the file does not exist.
    :param output_message: bool, if True, the function will print a message if the file does not exist.
    :return:
    """

    if not config_file_path:
        config_file_path = config_basic.ELASTIC_CONFIG_FILE

    # if not ubuntu_terminal.is_sudo_file_exists(config_file_path):
    if not filesystem.check_file_existence(config_file_path):
        if output_message:
            message = f"Configuration file does not exist at {config_file_path}."
            print_api(message, color='red', error_type=True)
        if exit_on_error:
            sys.exit(1)
        return False
    else:
        return True


def check_xpack_security_setting(config_file_path: str = None):
    """
    The function checks if the 'xpack.security.enabled' setting is set to 'false' in the Elasticsearch
    configuration file.

    :param config_file_path:
    :return:
    """

    if not config_file_path:
        config_file_path = config_basic.ELASTIC_CONFIG_FILE

    with open(config_file_path, 'r') as file:
        # Read the file contents
        contents = file.read()
        # Check if the specific setting exists
        if f"{config_basic.XPACK_SECURITY_SETTING_NAME}: false" in contents:
            return False
        elif f"{config_basic.XPACK_SECURITY_SETTING_NAME}: true" in contents:
            return True
        # If the setting doesn't exist, return None.
        else:
            return None


def modify_xpack_security_setting(
        config_file_path: str = None,
        setting: bool = False,
        output_message: bool = True
):
    """
    The function modifies the 'xpack.security.enabled' setting in the Elasticsearch configuration file.
    :param config_file_path: str, the path to the configuration file.
    :param setting: bool, the setting to change to. Will be added, if doesn't exist.
    :param output_message: bool, if True, the function will print a message.
    :return:
    """

    if not config_file_path:
        config_file_path = config_basic.ELASTIC_CONFIG_FILE

    # The setting to set in the configuration file.
    xpack_setting_to_set: str = f'{config_basic.XPACK_SECURITY_SETTING_NAME}: {str(setting).lower()}'

    # Check if the setting exists in the configuration file and get its value.
    current_xpack_security_setting = check_xpack_security_setting(config_file_path)

    # If the setting doesn't exist, add it to the configuration file.
    if current_xpack_security_setting is None:
        with open(config_file_path, 'a') as file:
            file.write(f'{xpack_setting_to_set}\n')
        if output_message:
            print_api(f"Added [{xpack_setting_to_set}] to the configuration.")
    # If the setting exists and is different from the desired setting, change it.
    elif current_xpack_security_setting != setting:
        with open(config_file_path, 'r') as file:
            lines = file.readlines()
        with open(config_file_path, 'w') as file:
            for line in lines:
                if f"{config_basic.XPACK_SECURITY_SETTING_NAME}:" in line:
                    file.write(f'{xpack_setting_to_set}\n')
                else:
                    file.write(line)
        if output_message:
            print_api(f"Changed [{config_basic.XPACK_SECURITY_SETTING_NAME}] to [{setting}].")
    # If the setting is already set to the desired value, print a message.
    elif current_xpack_security_setting == setting:
        if output_message:
            print_api(f"The setting is already set to [{setting}].")


def create_jvm_options_custom_file(file_path: str, options: list):
    """
    The function creates a custom JVM options file for Elasticsearch.
    You can use the default directory path as 'config_basic.ELASTIC_JVM_OPTIONS_DIRECTORY'.
    :param file_path: str, the path to the custom JVM options file.
    :param options: list, the list of JVM options.
    :return:
    """

    # Write the options to the file.
    with open(file_path, 'w') as file:
        for option in options:
            file.write(f"{option}\n")


def create_jvm_options_custom_4gb_memory_heap_file(file_path: str = None):
    """
    The function creates a custom JVM options file with 4GB memory heap usage.
    The 4GB memory usage options are needed for the Elasticsearch to work properly and not to crash.
    :param file_path: str, the path to the custom JVM options file.
    :return:
    """

    if not file_path:
        file_path = config_basic.ELASTIC_JVM_OPTIONS_4GB_CUSTOM_FILE

    create_jvm_options_custom_file(file_path, config_basic.ELASTIC_JVM_OPTIONS_4GB_MEMORY_USAGE)


def is_server_available(
        max_attempts: int = 5,
        wait_between_attempts_seconds: float = 10,
        elastic_url: str = None,
        print_kwargs: dict = None
):
    """
    The function checks if Elasticsearch server is up and running by sending GET request to the Elasticsearch server.
    :param max_attempts: int, the maximum number of attempts to check if Elasticsearch is running.
    :param wait_between_attempts_seconds: float, the time to wait between attempts.
    :param elastic_url: str, the URL of the Elasticsearch server. If None, the default URL will be used.
    :param print_kwargs: dict, the keyword arguments for the print_api function.
    :return:
    """

    if not elastic_url:
        elastic_url = config_basic.DEFAULT_ELASTIC_URL

    if not print_kwargs:
        print_kwargs = dict()

    for attempt in range(1, max_attempts + 1):
        print_api(f"Checking if Elasticsearch is running (Attempt {attempt}/{max_attempts})...", **print_kwargs)

        try:
            response = requests.get(elastic_url)
            status_code = response.status_code

            if status_code == 200:
                print_api("Elasticsearch is up and running.", color='green', **print_kwargs)
                return True
            else:
                print_api(f"Elasticsearch is not running. Status code: {status_code}", color='yellow', **print_kwargs)
        except requests.exceptions.RequestException as e:
            print_api(f"Failed to connect to Elasticsearch: {e}", color='yellow', **print_kwargs)

        print_api("Waiting for Elasticsearch to start...", **print_kwargs)
        time.sleep(wait_between_attempts_seconds)

    print_api("Elasticsearch did not start within the expected time.", color='red', **print_kwargs)
    return False


def is_4gb_memory_heap_options_applied_on_server() -> bool:
    """
    The function checks if the 4GB memory heap options are applied on the Elasticsearch server.
    :return: bool.
    """

    # Send a GET request
    response = requests.get(config_basic.DEFAULT_ELASTIC_URL_JVM_OPTIONS)
    response.raise_for_status()  # Raise an exception for HTTP errors

    # Load JSON data from the response
    jvm_data = response.json()

    # Check if memory heap options are applied in 'input_arguments' key.
    for node in jvm_data['nodes'].values():
        # Get the JVM input arguments values.
        input_arguments = node['jvm']['input_arguments']

        # Check that the 4GB memory heap options are applied.
        return all(options in input_arguments for options in config_basic.ELASTIC_JVM_OPTIONS_4GB_MEMORY_USAGE)

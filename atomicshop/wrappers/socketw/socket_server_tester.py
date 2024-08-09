import threading

from .socket_client import SocketClient
from ..configparserw import ConfigParserWrapper
from ..loggingw import loggingw
from ...filesystem import get_file_paths_from_directory
from ...file_io import jsons, file_io


def get_key_values_from_json(json_dict: dict, extract_keys: list):
    """ The function iterates through the keys and checks if they are in the json content. If so returns the value of
    the key.

    :param extract_keys: List of keys that will be checked against json content.
    :param json_dict: The content of single json. Can be list or dict. List also can contain only single json.
    :return: Return list of values of all the keys that inside json content.
    """

    # Iterate through all the keys in current key list.
    return_value_list: list = list()
    for key in extract_keys:
        # If the key in current JSON dict.
        if key in json_dict:
            # Get its value.
            current_hex_value = json_dict[key]
            # Convert value from hex to bytes.
            current_bytes_value = bytes.fromhex(current_hex_value)
            # Append the value to return list.
            return_value_list.append(current_bytes_value)

    print(f"Extracted requests for keys {extract_keys}: {len(return_value_list)}")
    return return_value_list


# =========================================
# Main
def execute_test(config_static):
    # Import config ini file and read it to dict.
    config_importer = ConfigParserWrapper(
        file_name=config_static.CONFIG_INI_TESTER_FILE_NAME, directory_path=config_static.WORKING_DIRECTORY)
    config_importer.read_to_dict()
    # Convert keys.
    config_importer.convert_string_values(
        key_list=[
            'target_port', 'interval_between_requests_defaults_seconds', 'send_request_batch_cycles',
            'interval_between_batch_cycles_seconds'
        ], convert_type='int')
    config_importer.convert_string_values(key_list=['parallel_connections_bool'], convert_type='bool')
    config_importer.convert_string_values(key_list=['request_json_hex_key_list'], convert_type='list')
    config_importer.convert_string_values(
        key_list=['interval_between_request_custom_list_seconds'], convert_type='list_of_int')
    config_importer.convert_string_values(key_list=['requests_directory'], convert_type='path_relative_to_full')
    # Get the config.
    config = config_importer.config['config']

    # SocketClient is working with 'network' logger by default, so we will initialize it.
    loggingw.get_logger_with_stream_handler("network")

    # Get all the files in requests folder recursively.
    request_file_list = get_file_paths_from_directory(config['requests_directory'])
    print(f"Found request files: {len(request_file_list)}")

    # Get contents of all request files to list of contents.
    requests_bytes_list: list = list()
    for request_file_path in request_file_list:
        if config['request_type'] == 'json':
            request_file_content = jsons.read_json_file(request_file_path)

            # If imported json is regular and not combined json.
            if isinstance(request_file_content, dict):
                # Append all the bytes values with specified keys from config.
                requests_bytes_list.extend(
                    get_key_values_from_json(request_file_content, config['request_json_hex_key_list']))
            # If imported json is combined json.
            if isinstance(request_file_content, list):
                # Iterate through all the dicts.
                for json_dict in request_file_content:
                    # Append all the bytes values with specified keys from config.
                    requests_bytes_list.extend(
                        get_key_values_from_json(json_dict, config['request_json_hex_key_list']))
        elif config['request_type'] == 'string':
            request_file_content = file_io.read_file(request_file_path)
            # Convert string content to bytes and append to list.
            requests_bytes_list.append(request_file_content.encode())
            print(f"Extracted 1 request.")
        elif config['request_type'] == 'binary':
            # The content is already in bytes, so just appending.
            requests_bytes_list.append(file_io.read_file(request_file_path, 'rb'))
            print(f"Extracted 1 request.")

    print(f"Finished parsing. Parsed requests: {len(requests_bytes_list)}")
    print(f"Initializing client to [{config['target_domain_or_ip']}:{config['target_port']}]")

    if not config['parallel_connections_bool']:
        # Initialize the class.
        socket_client = SocketClient(config['target_domain_or_ip'], config['target_port'])

        # Sending all the requests and getting responses
        responses_list, errors_list, server_ip = socket_client.send_receive_message_list_with_interval(
            requests_bytes_list,
            config['interval_between_request_custom_list_seconds'],
            config['interval_between_requests_defaults_seconds'],
            config['send_request_batch_cycles'])
    else:
        threads_list: list = list()
        for i in range(config['send_request_batch_cycles']):
            # If there are more cycles than 1
            if config['send_request_batch_cycles'] > 1:
                print(f"Starting cycle: {i + 1}")

            # Initialize the class.
            socket_client = SocketClient(config['target_domain_or_ip'], config['target_port'])
            # Send a function of the class to a thread.
            thread_current = threading.Thread(
                target=socket_client.send_receive_message_list_with_interval,
                args=(
                    requests_bytes_list,
                    config['interval_between_request_custom_list_seconds'],
                    config['interval_between_requests_defaults_seconds'],))
            thread_current.daemon = True
            # Start the thread
            thread_current.start()
            # Append to list of threads, so they can be "joined" later
            threads_list.append(thread_current)

        # Joining all the threads.
        for thread in threads_list:
            thread.join()

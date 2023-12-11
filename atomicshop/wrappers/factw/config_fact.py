from ...file_io import tomls
from ... import filesystem


FACT_ADDRESS: str = 'http://localhost:5000'
FIRMWARE_ENDPOINT: str = '/rest/firmware'
FILE_OBJECT_ENDPOINT: str = '/rest/file_object'
STATUS_ENDPOINT: str = '/rest/status'
STATISTICS_ENDPOINT: str = '/rest/statistics'
BINARY_SEARCH_ENDPOINT: str = '/rest/binary_search'
FACT_CONFIG_PATH: str = 'src/config/fact-core-config.toml'


def get_config_data(fact_core_path: str) -> dict:
    """
    Get the config data from the fact config file.
    :param fact_core_path: string, path to the 'FACT_core' directory, including the 'FACT_core' in the path.
    :return: dict, config data.
    """

    fact_core_path = filesystem.add_last_separator(fact_core_path)
    fact_config_path: str = f'{fact_core_path}{FACT_CONFIG_PATH}'

    config_data: dict = tomls.read_toml_file(fact_config_path)

    return config_data

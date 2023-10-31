# noinspection PyPackageRequirements
import requests

from .. import fact_config
from .... print_api import print_api


def search_string(string_to_search: str):
    """
    Get the binaries by searching for a string.
    :return:
    """

    yara_rule = {
        "rule_file": "rule rulename {strings: $a = \"" + string_to_search + "\" condition: $a }"
    }

    url: str = f'{fact_config.FACT_ADDRESS}{fact_config.BINARY_SEARCH_ENDPOINT}'
    response: requests.Response = requests.get(url, json=yara_rule)

    # Check response status code.
    if response.status_code == 200:
        # Print response.
        print_api(response.json())
    else:
        # Print error.
        print_api('Error: ' + str(response.status_code), error_type=True, logger_method='critical')

    return response

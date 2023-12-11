# noinspection PyPackageRequirements
import requests

from .. import config_fact
from .... print_api import print_api


def get_statistics():
    """
    Get statistics of the FACT service.
    :return:
    """

    url: str = f'{config_fact.FACT_ADDRESS}{config_fact.STATISTICS_ENDPOINT}'
    response: requests.Response = requests.get(url)

    # Check response status code.
    if response.status_code == 200:
        # Print response.
        print_api(response.json())
    else:
        # Print error.
        print_api('Error: ' + str(response.status_code), error_type=True, logger_method='critical')

    return response

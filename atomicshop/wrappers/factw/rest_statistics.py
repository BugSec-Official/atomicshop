# noinspection PyPackageRequirements
import requests

from . import fact_config
from ... print_api import print_api


def get_statistics():
    """
    Get statistics of the FACT service.
    :return:
    """

    url: str = f'{fact_config.FACT_ADDRESS}{fact_config.STATISTICS_ENDPOINT}'
    response: requests.Response = requests.get(url)

    # Check response status code.
    if response.status_code == 200:
        # Print response.
        print_api(response.json())
    else:
        # Print error.
        print_api('Error: ' + str(response.status_code), error_type=True, logger_method='critical')

    return response

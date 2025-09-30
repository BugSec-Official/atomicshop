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

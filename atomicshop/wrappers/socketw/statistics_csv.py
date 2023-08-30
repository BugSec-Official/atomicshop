import datetime

from ...print_api import print_api


def write_accept_error(error_message: str, host: str, process_name: str, statistics_logger, print_kwargs: dict = None):
    request_time_sent = datetime.datetime.now()

    # If 'message' is not defined, it means there was no execution and there is no need for statistics.
    try:
        statistics_logger.info(
            f"{request_time_sent},"
            f"{host},"
            f",,,,,,"
            f"\"{process_name}\","
            f"{error_message}"
        )
    except UnboundLocalError:
        pass
    except Exception:
        message = "Undocumented exception after accept on building statistics."
        print_api(message, error_type=True, logger_method='error', traceback_string=True, oneline=True, **print_kwargs)
        pass

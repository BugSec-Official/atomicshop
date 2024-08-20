import datetime

from ...print_api import print_api
from ...file_io import csvs
from ..loggingw import loggingw


LOGGER_NAME: str = 'statistics'
STATISTICS_HEADER: str = \
    ('request_time_sent,tls,protocol,host,path,command,status_code,request_size_bytes,response_size_bytes,file_path,'
     'process_cmd,error')


class StatisticsCSVWriter:
    """
    Class to write statistics to CSV file.
    This can be initiated at the main, and then passed to the thread worker function.
    """
    def __init__(
            self,
            statistics_directory_path: str
    ):
        self.statistics_directory_path = statistics_directory_path

        self.csv_logger = loggingw.create_logger(
            logger_name=LOGGER_NAME,
            directory_path=statistics_directory_path,
            add_timedfile=True,
            formatter_filehandler='MESSAGE',
            file_type='csv',
            header=STATISTICS_HEADER
        )

    def write_row(
            self,
            host: str,
            tls_type: str,
            tls_version: str,
            protocol: str,
            path: str,
            status_code: str,
            command: str,
            request_size_bytes: str,
            response_size_bytes: str,
            recorded_file_path: str = None,
            process_cmd: str = None,
            error: str = None,
            request_time_sent=None,
    ):
        if not request_time_sent:
            request_time_sent = datetime.datetime.now()

        if not tls_type and not tls_version:
            tls_info = ''
        else:
            tls_info = f'{tls_type}|{tls_version}'

        escaped_line_string: str = csvs.escape_csv_line_to_string([
            request_time_sent,
            tls_info,
            protocol,
            host,
            path,
            command,
            status_code,
            request_size_bytes,
            response_size_bytes,
            recorded_file_path,
            process_cmd,
            error
        ])

        self.csv_logger.info(escaped_line_string)

    def write_accept_error(
            self,
            error_message: str,
            host: str,
            process_name: str
    ):
        """
        Write the error message to the statistics CSV file.
        This is used for easier execution, since most of the parameters will be empty on accept.

        :param error_message: string, error message.
        :param host: string, host, the domain or IP address.
        :param process_name: process name, the command line of the process.
        :return:
        """

        self.write_row(
            host=host,
            tls_type='',
            tls_version='',
            protocol='',
            path='',
            status_code='',
            command='',
            request_size_bytes='',
            response_size_bytes='',
            recorded_file_path='',
            process_cmd=process_name,
            error=error_message
        )

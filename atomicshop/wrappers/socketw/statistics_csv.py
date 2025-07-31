import datetime
import multiprocessing

from ..loggingw import loggingw


LOGGER_NAME: str = 'statistics'
STATISTICS_HEADER: str = (
    'request_time_sent,thread_id,engine,source_host,source_ip,tls,protocol,protocol2,protocol3,dest_port,host,path,command,status_code,request_size_bytes,'
    'response_size_bytes,file_path,process_cmd,action,error')


class StatisticsCSVWriter(loggingw.CsvLogger):
    """
    Class to write statistics to CSV file.
    This can be initiated at the main, and then passed to the thread worker function.
    """
    def __init__(
            self,
            logger_name: str = LOGGER_NAME,
            directory_path: str = None,
            log_queue: multiprocessing.Queue = None,
            add_queue_handler_start_listener_multiprocessing: bool = False,
            add_queue_handler_no_listener_multiprocessing: bool = False
    ):
        """
        Initialize the StatisticsCSVWriter with the directory path for the statistics CSV file.
        :param directory_path: str, the directory path where the statistics CSV file will be created.
        :param log_queue: multiprocessing.Queue, the queue to use for logging in multiprocessing.
        :param add_queue_handler_start_listener_multiprocessing: bool, whether to add a queue handler that will use
            the 'logger_queue' and start the queue listener with the same 'logger_queue' for multiprocessing.
        :param add_queue_handler_no_listener_multiprocessing: bool, whether to add a queue handler that will use
            the 'logger_queue' but will not start the queue listener for multiprocessing. This is useful when you
            already started the queue listener and want to add more handlers to the logger without
            starting a new listener.

        If you don't set any of 'add_queue_handler_start_listener_multiprocessing' or
        'add_queue_handler_no_listener_multiprocessing', the logger will be created without a queue handler.
        """

        super().__init__(
            logger_name=logger_name,
            directory_path=directory_path,
            log_queue=log_queue,
            add_queue_handler_start_listener_multiprocessing=add_queue_handler_start_listener_multiprocessing,
            add_queue_handler_no_listener_multiprocessing=add_queue_handler_no_listener_multiprocessing,
            custom_header=STATISTICS_HEADER
        )

    def write_row(
            self,
            thread_id: str,
            engine: str,
            source_host: str,
            source_ip: str,
            host: str,
            tls_type: str,
            tls_version: str,
            protocol: str,
            protocol2: str,
            protocol3: str,
            dest_port: str,
            path: str,
            status_code: str,
            command: str,
            request_size_bytes: str,
            response_size_bytes: str,
            recorded_file_path: str = None,
            process_cmd: str = None,
            error: str = None,
            action: str = None,
            timestamp=None,
    ):
        if not timestamp:
            timestamp = datetime.datetime.now()

        if not tls_type and not tls_version:
            tls_info = ''
        else:
            tls_info = f'{tls_type}|{tls_version}'

        row_of_cols: list = [
            timestamp,
            thread_id,
            engine,
            source_host,
            source_ip,
            tls_info,
            protocol,
            protocol2,
            protocol3,
            dest_port,
            host,
            path,
            command,
            status_code,
            request_size_bytes,
            response_size_bytes,
            recorded_file_path,
            process_cmd,
            action,
            error
        ]

        super().write(row_of_cols)

    def write_accept_error(
            self,
            engine: str,
            source_ip: str,
            source_host: str,
            error_message: str,
            dest_port: str,
            host: str,
            process_name: str,
            thread_id: str = str()
    ):
        """
        Write the error message to the statistics CSV file.
        This is used for easier execution, since most of the parameters will be empty on accept.

        :param engine: string, engine name.
        :param source_ip: string, source IP address.
        :param source_host: string, source host name.
        :param error_message: string, error message.
        :param dest_port: string, destination port.
        :param host: string, host, the domain or IP address.
        :param process_name: process name, the command line of the process.
        :param thread_id: integer, the id of the thread.
        :return:
        """

        self.write_row(
            thread_id=thread_id,
            engine=engine,
            source_host=source_host,
            source_ip=source_ip,
            tls_type='',
            tls_version='',
            protocol='',
            protocol2='',
            protocol3='',
            dest_port=dest_port,
            host=host,
            path='',
            status_code='',
            command='',
            request_size_bytes='',
            response_size_bytes='',
            recorded_file_path='',
            process_cmd=process_name,
            action='client_accept',
            error=error_message
        )

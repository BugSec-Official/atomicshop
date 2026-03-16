import copy
import os
from datetime import datetime
import queue
import threading
from pathlib import Path

from ...shared_functions import build_module_names, create_custom_logger
from ... import message, recs_files, config_static
from .... import filesystem
from ....file_io import jsons
from ....print_api import print_api

PCAP_QUEUE = None  # multiprocessing.Queue, set by _create_tcp_server_process


# The class that is responsible for Recording Requests / Responses.
class RecorderParent:

    # noinspection PyTypeChecker
    def __init__(self, record_path: str):
        self.record_path: str = record_path

        self.file_extension: str = ".json"
        self.engine_name = None
        self.module_name = None
        self.engine_record_path: str = str()
        self.record_file_path: str = str()
        self.class_client_message: message.ClientMessage = None

        self.logger = create_custom_logger()

        # Get engine name and module name
        self.get_engine_module()

        # Build the record path with file name
        self.build_record_path_to_engine()

        # Create folder.
        filesystem.create_directory(self.engine_record_path)

        # Initialize a queue to hold messages
        self.message_queue: queue.Queue = queue.Queue()
        self.recorder_worker_thread = None

    # "self.__module__" is fully qualified module name: classes.engines.ENGINE-NAME.MODULE-NAME
    def get_engine_module(self):
        _, self.engine_name, self.module_name = build_module_names(self.__module__)

    def build_record_path_to_engine(self):
        self.engine_record_path = self.record_path + os.sep + self.engine_name

    def build_record_full_file_path(self):
        # If HTTP Path is not defined, 'http_path' will be empty, and it will not interfere with file name.
        self.record_file_path: str = (
            f"{self.engine_record_path}{os.sep}th{self.class_client_message.thread_id}_"
            f"{self.class_client_message.server_name}{self.file_extension}")

    def convert_messages(self):
        """
        Function to convert raw byte requests and responses to hex if they're not empty.
        """

        # We need to check that the values that we want to convert aren't empty or 'None'.
        if self.class_client_message.request_raw_bytes:
            self.class_client_message.request_raw_hex = self.class_client_message.request_raw_bytes.hex()
        if self.class_client_message.response_raw_bytes:
            self.class_client_message.response_raw_hex = self.class_client_message.response_raw_bytes.hex()

    def record(
            self,
            class_client_message: message.ClientMessage
    ):
        self.class_client_message = class_client_message

        # Build full file path if it is not already built.
        if not self.record_file_path:
            self.build_record_full_file_path()

        # Start the worker thread if it is not already running
        if not self.recorder_worker_thread:
            self.recorder_worker_thread = threading.Thread(
                target=save_message_worker,
                args=(self.record_file_path, self.message_queue, self.logger),
                name=f"{self.class_client_message.thread_process}-{class_client_message.destination_port}-Recorder",
                daemon=True
            )
            self.recorder_worker_thread.start()

        self.logger.info("Putting Message to Recorder Thread Queue...")

        # Put a copy of the client message object to the queue,
        # so the worker can convert to JSON and/or pcap independently.
        self.message_queue.put(copy.copy(self.class_client_message))

        return self.record_file_path


def save_message_worker(
        record_file_path_no_date: str,
        message_queue: queue.Queue,
        logger
):
    """Worker function to process messages from the queue and write them to the file."""
    original_file_path_object: Path = Path(record_file_path_no_date)
    original_file_stem: str = original_file_path_object.stem
    original_file_extension: str = original_file_path_object.suffix
    original_file_directory: str = str(original_file_path_object.parent)

    original_datetime_string: str = get_datetime_string()
    previous_date_string: str = get_date_string()

    record_file_path: str = f'{original_file_directory}{os.sep}{original_datetime_string}_{original_file_stem}{original_file_extension}'

    while True:
        # Get a message from the queue
        class_client_message = message_queue.get()

        # Check for the "stop" signal
        if class_client_message is None:
            break

        current_date_string: str = get_date_string()

        # If current date is different, create new file paths.
        if current_date_string != previous_date_string:
            previous_date_string = current_date_string
            current_datetime_string: str = get_datetime_string()
            record_file_path = f'{original_file_directory}{os.sep}{current_datetime_string}_{original_file_stem}_partof_{original_datetime_string}{original_file_extension}'

        # Write JSON if enabled.
        if config_static.LogRec.record_json:
            # Convert raw bytes to hex for JSON serialization.
            if class_client_message.request_raw_bytes:
                class_client_message.request_raw_hex = class_client_message.request_raw_bytes.hex()
            if class_client_message.response_raw_bytes:
                class_client_message.response_raw_hex = class_client_message.response_raw_bytes.hex()

            record_message_dict: dict = dict(class_client_message)

            try:
                jsons.append_to_json(
                    record_message_dict, record_file_path, indent=2,
                    enable_long_file_path=True, print_kwargs={'logger': logger}
                )
            except TypeError as e:
                print_api(str(e), logger_method="critical", logger=logger)
                raise e

            logger.info(f"Recorded to file: {record_file_path}")

        # Write pcap if enabled — send data to the pcap writer process via queue.
        if config_static.LogRec.record_pcap and PCAP_QUEUE is not None:
            if class_client_message.action == "client_receive":
                raw_bytes = class_client_message.request_raw_bytes
                source_ip = class_client_message.client_ip
                source_port = class_client_message.source_port
                dest_ip = class_client_message.server_ip
                dest_port = class_client_message.destination_port
                timestamp = int(class_client_message.timestamp.timestamp())
            elif class_client_message.action == "service_receive":
                raw_bytes = class_client_message.response_raw_bytes
                source_ip = class_client_message.server_ip
                source_port = class_client_message.destination_port
                dest_ip = class_client_message.client_ip
                dest_port = class_client_message.source_port
                timestamp = int(class_client_message.timestamp.timestamp())
            else:
                raw_bytes = None

            if raw_bytes is not None:
                PCAP_QUEUE.put({
                    'engine_dir': original_file_directory,
                    'source_ip': source_ip,
                    'dest_ip': dest_ip,
                    'source_port': source_port,
                    'dest_port': dest_port,
                    'raw_bytes': raw_bytes,
                    'timestamp': timestamp,
                    'thread_id': class_client_message.thread_id,
                    'process_name': class_client_message.process_name
                })

        # Indicate task completion
        message_queue.task_done()


def get_datetime_string():
    # current date and time in object
    now = datetime.now()
    # Formatting the date and time and converting it to string object
    day_time_format: str = now.strftime(recs_files.REC_FILE_DATE_TIME_FORMAT)
    return day_time_format

def get_date_string():
    # current date and time in object
    now = datetime.now()
    # Formatting the date and time and converting it to string object
    date_format: str = now.strftime(recs_files.REC_FILE_DATE_FORMAT)
    return date_format
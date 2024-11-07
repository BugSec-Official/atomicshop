import os
from datetime import datetime
import json
import queue
import threading

from ...shared_functions import build_module_names, create_custom_logger
from ... import message, recs_files
from .... import filesystem
from ....file_io import jsons
from ....print_api import print_api


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
        # current date and time in object
        now = datetime.now()
        # Formatting the date and time and converting it to string object
        day_time_format: str = now.strftime(recs_files.REC_FILE_DATE_TIME_FORMAT)

        # If HTTP Path is not defined, 'http_path' will be empty, and it will not interfere with file name.
        self.record_file_path: str = (
            f"{self.engine_record_path}{os.sep}{day_time_format}_th{self.class_client_message.thread_id}_"
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

    def record(self, class_client_message: message.ClientMessage):
        self.class_client_message = class_client_message

        # Build full file path if it is not already built.
        if not self.record_file_path:
            self.build_record_full_file_path()

        # Start the worker thread if it is not already running
        if not self.recorder_worker_thread:
            self.recorder_worker_thread = threading.Thread(
                target=save_message_worker,
                args=(self.record_file_path, self.message_queue, self.logger),
                name=f"Thread-{self.class_client_message.thread_id}_Recorder",
                daemon=True
            )
            self.recorder_worker_thread.start()

        self.logger.info("Recording Message...")

        # Convert the requests and responses to hex.
        self.convert_messages()
        # Get the message in dict / JSON format
        record_message_dict: dict = dict(self.class_client_message)

        # Put the message in the queue to be processed by the worker thread
        self.message_queue.put(record_message_dict)

        return self.record_file_path


def save_message_worker(
        record_file_path: str,
        message_queue: queue.Queue,
        logger
):
    """Worker function to process messages from the queue and write them to the file."""
    while True:
        # Get a message from the queue
        record_message_dict = message_queue.get()

        # Check for the "stop" signal
        if record_message_dict is None:
            break

        # Read existing data from the file
        try:
            with open(record_file_path, 'r') as f:
                current_json_file = json.load(f)
        except FileNotFoundError:
            current_json_file: list = []

        # Append the new message to the existing data
        final_json_list_of_dicts: list[dict] = []
        if isinstance(current_json_file, list):
            current_json_file.append(record_message_dict)
            final_json_list_of_dicts = current_json_file
        elif isinstance(current_json_file, dict):
            final_json_list_of_dicts.append(current_json_file)
            final_json_list_of_dicts.append(record_message_dict)
        else:
            error_message = "The current file is neither a list nor a dictionary."
            print_api(error_message, logger_method="critical", logger=logger)
            raise TypeError(error_message)

        # Write the data back to the file
        jsons.write_json_file(
            final_json_list_of_dicts, record_file_path, indent=2,
            enable_long_file_path=True, **{'logger': logger})

        logger.info(f"Recorded to file: {record_file_path}")

        # Indicate task completion
        message_queue.task_done()

import os
from datetime import datetime

from ...shared_functions import build_module_names, create_custom_logger, get_json
from ... import message, recs_files
from .... import filesystem, urls
from ....file_io import file_io


# The class that is responsible for Recording Requests / Responses.
class RecorderParent:

    def __init__(self, class_client_message: message.ClientMessage, record_path: str):
        self.class_client_message: message.ClientMessage = class_client_message
        self.record_path: str = record_path
        self.file_extension: str = ".json"
        self.engine_name = None
        self.module_name = None
        self.engine_record_path: str = str()
        self.record_file_path: str = str()

        self.logger = create_custom_logger()

        # Get engine name and module name
        self.get_engine_module()
        # Build full file path.
        self.build_record_full_file_path()

        # Create folder.
        filesystem.create_directory(self.engine_record_path)

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

        # Build the record path with file name
        self.build_record_path_to_engine()

        # Define empty 'http_path'.
        http_path: str = str()
        # If 'self.class_client_message.request_raw_decoded.path' will be undefined, exception will raise.
        # This will happen if the message is not HTTP.
        try:
            # Parse the url to components.
            http_path_parsed = urls.url_parser(self.class_client_message.request_raw_decoded.path)
            # Get only directories.
            http_path_directories_string = '-'.join(http_path_parsed['directories'])
            # Add '_' character before 'http_path' to look better on the file name.
            http_path = f'_{http_path_directories_string}'
        # If 'self.class_client_message.request_raw_decoded.path' is not defined, we'll pass the exception.
        except Exception:
            pass

        # If HTTP Path is not defined, 'http_path' will be empty, and it will not interfere with file name.
        self.record_file_path: str = \
            self.engine_record_path + os.sep + \
            day_time_format + "_" + self.class_client_message.server_name + self.file_extension

    def convert_messages(self):
        """
        Function to convert raw byte requests and responses to hex if they're not empty.
        """

        # We need to check that the values that we want to convert aren't empty or 'None'.
        if self.class_client_message.request_raw_bytes:
            self.class_client_message.request_raw_hex = self.class_client_message.request_raw_bytes.hex()
        if self.class_client_message.response_list_of_raw_bytes:
            # We checked that the list isn't empty, now we check if the first value is not empty, since if we
            # check it in the same expression as check for list is empty, we will get an exception since
            # the list is empty.
            if self.class_client_message.response_list_of_raw_bytes[0]:
                for response_raw_bytes in self.class_client_message.response_list_of_raw_bytes:
                    self.class_client_message.response_list_of_raw_hex.append(response_raw_bytes.hex())

    def record(self):
        self.logger.info("Recording Message...")

        # Convert the requests and responses to hex.
        self.convert_messages()
        # Get the message in dict / JSON format
        record_message = get_json(self.class_client_message)

        # Since we already dumped the object to dictionary string, we'll just save the object to regular file.
        file_io.write_file(record_message, self.record_file_path, enable_long_file_path=True, **{'logger': self.logger})

        self.logger.info(f"Recorded to file: {self.record_file_path}")

        return self.record_file_path

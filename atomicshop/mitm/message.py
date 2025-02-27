from datetime import datetime
from typing import Union

from .. import http_parse
from ..basics import dicts


class ClientMessage:
    """ A class that will store all the message details from the client """
    def __init__(self):
        # noinspection PyTypeChecker
        self.timestamp: datetime = None
        self.engine_name: str = str()
        # noinspection PyTypeChecker
        self.request_raw_bytes: bytes = None
        self.request_auto_parsed: Union[http_parse.HTTPRequestParse, any] = None
        self.request_custom_parsed: any = None
        self.request_raw_hex: hex = None
        # noinspection PyTypeChecker
        self.response_raw_bytes: bytes = None
        self.response_auto_parsed: any = None
        self.response_custom_parsed: any = None
        self.response_raw_hex: hex = None
        self.server_name: str = str()
        self.server_ip: str = str()
        self.client_name: str = str()
        self.client_ip: str = str()
        self.source_port: int = int()
        self.destination_port: int = int()
        self.process_name: str = str()
        self.thread_id = None
        self.info: str = str()
        self.errors: list = list()
        self.protocol: str = str()
        self.protocol2: str = str()
        self.protocol3: str = str()
        self.recorded_file_path: str = str()
        self.action: str = str()

    def reinitialize_dynamic_vars(self):
        """
        Reinitialize the dynamic variables of the class for the new cycle.
        """
        self.request_raw_bytes = None
        self.timestamp = None
        self.request_auto_parsed = None
        self.request_custom_parsed = None
        self.request_raw_hex = None
        self.response_raw_bytes = None
        self.response_auto_parsed = None
        self.response_custom_parsed = None
        self.response_raw_hex = None
        self.action = None
        self.info = str()
        self.errors = list()
        self.protocol = str()
        self.protocol2 = str()
        self.protocol3 = str()
        self.recorded_file_path = str()

    def __iter__(self):
        # __dict__ returns a dictionary containing the instance's attributes
        for key, value in self.__dict__.items():
            if key == 'request_raw_bytes':
                value = str(value)
            elif key == 'timestamp':
                value = value.strftime('%Y-%m-%d-%H:%M:%S.%f')
            elif key == 'request_auto_parsed':
                if isinstance(value, http_parse.HTTPRequestParse):
                    value = dicts.convert_complex_object_to_dict(value)
                else:
                    value = str(value)
            elif key == 'request_custom_parsed':
                value = dicts.convert_complex_object_to_dict(value)
            elif key == 'response_raw_bytes':
                value = str(value)
            elif key == 'response_auto_parsed':
                value = dicts.convert_complex_object_to_dict(value)
            yield key, value

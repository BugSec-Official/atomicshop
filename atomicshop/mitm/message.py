from datetime import datetime
from typing import Union

from .. import http_parse
from ..basics import dicts


class ClientMessage:
    """ A class that will store all the message details from the client """
    def __init__(self):
        self.request_raw_bytes: bytearray = bytearray()
        # noinspection PyTypeChecker
        self.request_time_received: datetime = None
        self.request_raw_decoded: Union[http_parse.HTTPRequestParse, any] = None
        self.request_body_parsed = None
        self.request_raw_hex: hex = None
        self.response_list_of_raw_bytes: list = list()
        self.response_list_of_raw_decoded: list = list()
        self.response_list_of_raw_hex: list = list()
        self.server_name: str = str()
        self.server_ip: str = str()
        self.client_ip: str = str()
        self.source_port: int = int()
        self.destination_port: int = int()
        self.process_name: str = str()
        self.thread_id = None
        self.info: str = str()
        self.error: str = str()
        self.protocol: str = str()
        self.recorded_file_path: str = str()

    def __iter__(self):
        # __dict__ returns a dictionary containing the instance's attributes
        for key, value in self.__dict__.items():
            if key == 'request_raw_bytes':
                value = str(value)
            elif key == 'request_time_received':
                value = value.strftime('%Y-%m-%d-%H:%M:%S.%f')
            elif key == 'request_raw_decoded':
                if isinstance(value, http_parse.HTTPRequestParse):
                    value = dicts.convert_complex_object_to_dict(value)
                else:
                    value = str(value)
            elif key == 'request_body_parsed':
                value = dicts.convert_complex_object_to_dict(value)
            elif key == 'response_list_of_raw_bytes':
                value = [str(bytes_response) for bytes_response in value]
            elif key == 'response_list_of_raw_decoded':
                value = [dicts.convert_complex_object_to_dict(complex_response) for complex_response in value]
            yield key, value

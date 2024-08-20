class ClientMessage:
    """ A class that will store all the message details from the client """
    def __init__(self):
        self.request_raw_bytes: bytearray = bytearray()
        self.request_time_received = None
        self.request_raw_decoded = None
        self.request_body_parsed = None
        self.request_raw_hex: hex = None
        # self.response_raw_bytes: bytearray = bytearray()
        self.response_list_of_raw_bytes: list = list()
        self.response_list_of_raw_decoded: list = list()
        # self.response_raw_hex: hex = None
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

    def reinitialize(self) -> None:
        """
        'ClientMessage' is being reused, since connection is still established to the server and new requests
        are being processed on the same socket, so we need to reinitialize variables that are being updated, like
        lists and dictionaries. Added the rest pf the variables that are repopulated to be on the safe side.
        :return:
        """

        self.request_raw_bytes = bytearray()
        self.request_time_received = None
        self.request_raw_decoded = None
        self.request_body_parsed = None
        self.response_list_of_raw_bytes = list()
        self.request_raw_hex = None
        self.response_list_of_raw_hex = list()
        self.response_list_of_raw_decoded = list()

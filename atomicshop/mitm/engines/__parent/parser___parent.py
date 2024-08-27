from ...shared_functions import create_custom_logger
from ...message import ClientMessage


class ParserParent:
    """Class that parses the message received from client."""
    def __init__(self, class_client_message: ClientMessage):
        self.class_client_message: ClientMessage = class_client_message
        self.logger = create_custom_logger()

    def parse(self):
        # This is general parser, so we don't parse anything and 'request_body_parsed' gets empty byte string.
        self.class_client_message.request_body_parsed = b''

        try:
            self.logger.info(f"Parsed: {self.class_client_message.request_body_parsed[0: 100]}...")
        except Exception:
            pass

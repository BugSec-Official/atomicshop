# v1.0.0 - 26.03.2023 14:00
from ...shared_functions import create_custom_logger
from ...message import ClientMessage


# Class that parses the message received from client.
class ParserParent:
    # Initializing the logger in the "class variable" section will leave the instance of the logger initiated
    # and the rest of the instances of the class will use the same logger.
    # It is not in the "__init__" section, so it's not going to be initiated again.
    # The name of the logger using "__name__" variable, which is the full name of the module package.
    # Example: classes.parsers.parser_1_reference_general

    # The code outside the functions will be executed during import of the module. When initializing a class
    # in the script these lines will not be called again, only the "init" function.
    logger = create_custom_logger()

    def __init__(self, class_client_message: ClientMessage):
        self.class_client_message: ClientMessage = class_client_message

    def parse(self):
        # This is general parser, so we don't parse anything and 'request_body_parsed' gets empty byte string.
        self.class_client_message.request_body_parsed = b''

        try:
            self.logger.info(f"Parsed: {self.class_client_message.request_body_parsed[0: 100]}...")
        except Exception:
            pass

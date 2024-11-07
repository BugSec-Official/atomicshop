import ssl
import logging
from pathlib import Path

from ...print_api import print_api
from ..loggingw import loggingw
from ...basics import tracebacks

from . import base


class Sender:
    def __init__(
            self,
            ssl_socket: ssl.SSLSocket,
            class_message: bytes,
            logger: logging.Logger = None
    ):
        self.class_message: bytes = class_message
        self.ssl_socket: ssl.SSLSocket = ssl_socket

        if logger:
            # Create child logger for the provided logger with the module's name.
            self.logger: logging.Logger = loggingw.get_logger_with_level(f'{logger.name}.{Path(__file__).stem}')
        else:
            self.logger: logging.Logger = logger

    # Function to send a message to server
    def send(self):
        # "socket.send()" returns number of bytes sent. "0" meaning that the socket was closed by the other side.
        # Unlike "send()" method, "socket.sendall()" doesn't return number of bytes at all. It sends all the data
        # until other side receives all, so there's no way knowing how much data was sent. Returns "None" on
        # Success though.

        # The error string that will be returned by the function in case of error.
        # If returned None then everything is fine.
        # noinspection PyTypeChecker
        error_message: str = None

        # Current amount of bytes sent is 0, since we didn't start yet
        total_sent_bytes = 0

        try:
            # Getting byte length of current message
            current_message_length = len(self.class_message)

            self.logger.info(
                f"Sending message to "
                f"{self.ssl_socket.getpeername()[0]}:{self.ssl_socket.getpeername()[1]}")

            # Looping through "socket.send()" method while total sent bytes are less than message length
            while total_sent_bytes < current_message_length:
                # Sending the message and getting the amount of bytes sent
                sent_bytes = self.ssl_socket.send(self.class_message[total_sent_bytes:])
                # If there were only "0" bytes sent, then connection on the other side was terminated
                if sent_bytes == 0:
                    error_message = (
                        f"Sent {sent_bytes} bytes - connection is down... Could send only "
                        f"{total_sent_bytes} bytes out of {current_message_length}. Closing socket...")
                    self.logger.info(error_message)
                    break

                # Adding amount of currently sent bytes to the total amount of bytes sent
                total_sent_bytes = total_sent_bytes + sent_bytes
                self.logger.info(f"Sent {total_sent_bytes} bytes out of {current_message_length}")

            # At this point the sending loop finished successfully
            self.logger.info(f"Sent the message to destination.")
        except Exception as e:
            source_tuple, destination_tuple = base.get_source_destination(self.ssl_socket)
            source_address, source_port = source_tuple
            destination_address, destination_port = destination_tuple
            if self.ssl_socket.server_hostname:
                destination_address = self.ssl_socket.server_hostname
            destination: str = f'[{source_address}:{source_port}<->{destination_address}:{destination_port}]'

            error_class_type = type(e).__name__
            exception_error = tracebacks.get_as_string(one_line=True)

            if 'ssl' in error_class_type.lower():
                if error_class_type in ['ssl.SSLEOFError', 'ssl.SSLZeroReturnError', 'ssl.SSLWantWriteError']:
                    error_message = f"Socket Send: {destination}: {error_class_type}: {exception_error}"
                else:
                    error_message = (f"Socket Send: {destination}: "
                                     f"SSL UNDOCUMENTED Exception: {error_class_type}{exception_error}")
            else:
                if error_class_type == 'ConnectionResetError':
                    error_message = (f"Socket Send: {destination}: "
                                     f"Error, Couldn't reach the server - Connection was reset | "
                                     f"{error_class_type}: {exception_error}")
                elif error_class_type in ['TimeoutError']:
                    error_message = f"Socket Send: {destination}: {error_class_type}: {exception_error}"
                else:
                    raise e

        if error_message:
            print_api(error_message, logger=self.logger, logger_method='error')

        return error_message

# v1.0.2 - 02.04.2023 17:30
import ssl

from ..print_api import print_api
from ..wrappers.loggingw import loggingw


class Sender:
    logger = loggingw.get_logger_with_level("network." + __name__.rpartition('.')[2])

    def __init__(self, ssl_socket: ssl.SSLSocket, class_message: bytearray):
        self.class_message: bytearray = class_message
        self.ssl_socket: ssl.SSLSocket = ssl_socket

    # Function to send a message to server
    def send(self):
        # "socket.send()" returns number of bytes sent. "0" meaning that the socket was closed by the other side.
        # Unlike "send()" method, "socket.sendall()" doesn't return number of bytes at all. It sends all the data
        # until other side receives all, so there's no way knowing how much data was sent. Returns "None" on
        # Success though.

        # Defining function result variable which will mean if the socket was closed or not.
        # True means everything is fine
        function_result: bool = True
        # Current amount of bytes sent is 0, since we didn't start yet
        total_sent_bytes = 0

        try:
            # Getting byte length of current message
            current_message_length = len(self.class_message)

            self.logger.info(f"Sending message to "
                             f"{self.ssl_socket.getpeername()[0]}:{self.ssl_socket.getpeername()[1]}")

            # Looping through "socket.send()" method while total sent bytes are less than message length
            while total_sent_bytes < current_message_length:
                # Sending the message and getting the amount of bytes sent
                sent_bytes = self.ssl_socket.send(self.class_message[total_sent_bytes:])
                # If there were only "0" bytes sent, then connection on the other side was terminated
                if sent_bytes == 0:
                    self.logger.info(f"Sent {sent_bytes} bytes - connection is down... Could send only "
                                     f"{total_sent_bytes} bytes out of {current_message_length}. Closing socket...")
                    function_result = False
                    break

                # Adding amount of currently sent bytes to the total amount of bytes sent
                total_sent_bytes = total_sent_bytes + sent_bytes
                self.logger.info(f"Sent {total_sent_bytes} bytes out of {current_message_length}")

            # At this point the sending loop finished successfully
            self.logger.info(f"Sent the message to destination.")
        except ConnectionResetError:
            message = "* Couldn't reach the server - Connection was reset. Exiting..."
            print_api(message, logger=self.logger, logger_method='critical', traceback_string=True, oneline=True)
            # Since the connection is down, it will be handled in thread_worker_main
            function_result = False
            pass
        except ssl.SSLEOFError:
            message = "SSLError on send, Exiting..."
            print_api(message, logger=self.logger, logger_method='critical', traceback_string=True, oneline=True)
            # Since the connection is down, it will be handled in thread_worker_main
            function_result = False
            pass
        except ssl.SSLZeroReturnError:
            message = "TLS/SSL connection has been closed (EOF), Exiting..."
            print_api(message, logger=self.logger, logger_method='critical', traceback_string=True, oneline=True)
            # Since the connection is down, it will be handled in thread_worker_main
            function_result = False
            pass

        return function_result

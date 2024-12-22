import logging
import socket
import ssl
import time

import select
from pathlib import Path

from ...print_api import print_api
from ..loggingw import loggingw


def peek_first_bytes(client_socket, bytes_amount: int = 1) -> bytes:
    """
    Peek first byte from the socket without removing it from the buffer.

    :param client_socket: Socket object.
    :param bytes_amount: Amount of bytes to peek.

    :return: the first X bytes from the socket buffer.
    """

    return client_socket.recv(bytes_amount, socket.MSG_PEEK)


def is_socket_ready_for_read(socket_instance, timeout: int = 0) -> bool:
    """
    Check if socket is ready for read.

    :param socket_instance: Socket object.
    :param timeout: Timeout in seconds. The default is no timeout.

    :return: True if socket is ready for read, False otherwise.
    """

    # Check if the socket is closed.
    if socket_instance.fileno() == -1:
        return False

    # Use select to check if the socket is ready for reading.
    # 'readable' returns a list of sockets that are ready for reading.
    # Since we use only one socket, it will return a list with one element if the socket is ready for reading,
    # or an empty list if the socket is not ready for reading.
    readable, _, _ = select.select([socket_instance], [], [], timeout)
    return bool(readable)


class Receiver:
    """ Receiver Class is responsible for receiving the message from socket and populate the message class """
    def __init__(
            self,
            ssl_socket: ssl.SSLSocket,
            logger: logging.Logger = None
    ):
        self.ssl_socket: ssl.SSLSocket = ssl_socket
        self.buffer_size_receive: int = 16384
        # Timeout of 2 is enough for regular HTTP sessions`.
        # Timeout on send to service servers dropped after 120 seconds
        # 60 seconds * 60 = minute * 60 = 1 hour
        # self.socket_timeout: int = 60*60
        # For current debugging purposes we'll set short timeout
        self.socket_timeout: int = 60
        # Optional return socket timeout to default
        # function_socket_object.settimeout(None)

        # Will get client address from the socket
        self.class_client_address: str = str()
        # Will get client Local port from the socket
        self.class_client_local_port: int = int()

        if logger:
            # Create child logger for the provided logger with the module's name.
            self.logger: logging.Logger = loggingw.get_logger_with_level(f'{logger.name}.{Path(__file__).stem}')
        else:
            self.logger: logging.Logger = logger

    # Function to receive only the buffer, with error handling
    def chunk_from_buffer(self) -> tuple[bytes, str]:
        """
        Receive a chunk from the socket buffer.

        :return: Tuple(received chunk binary bytes data, error message string).
        """
        # Defining the data variable
        # noinspection PyTypeChecker
        received_data: bytes = None
        # noinspection PyTypeChecker
        error_message: str = None

        # All excepts will be treated as empty message, indicate that socket was closed and will be handled properly.
        try:
            # "recv(byte buffer size)" to read the server's response.
            # A signal to close connection will be empty bytes string: b''.
            received_data = self.ssl_socket.recv(self.buffer_size_receive)
        except ConnectionAbortedError:
            error_message = "* Connection was aborted by the client. Exiting..."
            print_api(error_message, logger=self.logger, logger_method='critical', traceback_string=True)
        except ConnectionResetError:
            error_message = "* Connection was forcibly closed by the client. Exiting..."
            print_api(error_message, logger=self.logger, logger_method='critical', traceback_string=True)
        except ssl.SSLError:
            error_message = "* Encountered SSL error on packet receive. Exiting..."
            print_api(error_message, logger=self.logger, logger_method='critical', traceback_string=True)

        if received_data == b'':
            self.logger.info("Empty message received, socket closed on the other side.")

        return received_data, error_message

    def socket_receive_message_full(self) -> tuple[bytes, bool, str]:
        """
        Receive the full message from the socket.

        :return: Tuple(full data binary bytes, is socket closed boolean, error message string).
        """
        # Define the variable that is going to aggregate the whole data received
        full_data: bytes = bytes()
        # noinspection PyTypeChecker
        error_message: str = None

        # Infinite loop to accept data from the client
        # We'll skip the 'is_socket_ready_for_read' check on the first run, since we want to read the data anyway,
        # to leave the socket in the blocking mode.
        first_run: bool = True
        no_data_first_cycle: bool = True
        while True:
            # Check if there is data to be read from the socket.
            is_there_data: bool = is_socket_ready_for_read(self.ssl_socket, timeout=0)

            # If there is no data to be read from the socket, and it is the first cycle, wait for a bit and try again.
            if no_data_first_cycle and not is_there_data:
                no_data_first_cycle = False
                sleep_time: float = 0.5
                self.logger.info(f"First time socket not ready. Waiting {str(sleep_time)} seconds before trying last time.")
                time.sleep(sleep_time)
                continue

            # noinspection PyTypeChecker
            if is_there_data or first_run:
                first_run = False
                # Receive the data from the socket.
                received_chunk, error_message = self.chunk_from_buffer()
                received_chunk: bytes
                error_message: str

                # And if the message received is not empty then aggregate it to the main "data received" variable
                if received_chunk != b'' and received_chunk is not None:
                    full_data += received_chunk

                    self.logger.info(f"Received packet bytes: [{len(received_chunk)}] | "
                                     f"Total aggregated bytes: [{len(full_data)}]")

                elif received_chunk == b'' or received_chunk is None:
                    # If there received_chunk is None, this means that the socket was closed,
                    # since it is a connection error.
                    # Same goes for the empty message.
                    is_socket_closed = True
                    break
            else:
                # If there is no data to be read from the socket, it doesn't mean that the socket is closed.
                is_socket_closed = False
                received_chunk = None
                break

        if full_data:
            self.logger.info(f"Received total: [{len(full_data)}] bytes")

        # In case the full data is empty, and the received chunk is None, it doesn't mean that the socket is closed.
        # But it means that there was no data to be read from the socket, because of error or timeout.
        if full_data == b'' and received_chunk is None:
            full_data = None

        return full_data, is_socket_closed, error_message

    def receive(self) -> tuple[bytes, bool, str]:
        """
        Receive the message from the socket.

        :return: Tuple(
            data binary bytes,
            is socket closed boolean,
            error message string if there was a connection exception).
        """
        # Getting client address and Local port from the socket
        self.class_client_address = self.ssl_socket.getpeername()[0]
        self.class_client_local_port = self.ssl_socket.getpeername()[1]

        # Receiving data from the socket and closing the socket if send is finished.
        self.logger.info(f"Waiting for data from {self.class_client_address}:{self.class_client_local_port}")
        socket_data_bytes, is_socket_closed, error_message = self.socket_receive_message_full()
        socket_data_bytes: bytes
        is_socket_closed: bool
        error_message: str

        if socket_data_bytes:
            # Put only 100 characters to the log, since we record the message any way in full - later.
            self.logger.info(f"Received: {socket_data_bytes[0: 100]}...")

        return socket_data_bytes, is_socket_closed, error_message

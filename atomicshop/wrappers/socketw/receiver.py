import logging
import socket
import ssl
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


def is_socket_ready_for_read(client_socket, timeout: int = 0) -> bool:
    """
    Check if socket is ready for read.

    :param client_socket: Socket object.
    :param timeout: Timeout in seconds. The default is no timeout.

    :return: True if socket is ready for read, False otherwise.
    """

    # Use select to check if the socket is ready for reading.
    # 'readable' returns a list of sockets that are ready for reading.
    # Since we use only one socket, it will return a list with one element if the socket is ready for reading,
    # or an empty list if the socket is not ready for reading.
    readable, _, _ = select.select([client_socket], [], [], timeout)
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
    def socket_receive_message_buffer(self):
        # Defining the data variable
        class_data: bytes = bytes()

        try:
            # "recv(byte buffer size)" to read the server's response.
            class_data = self.ssl_socket.recv(self.buffer_size_receive)
        except ConnectionAbortedError:
            message = "* Connection was aborted by the client. Exiting..."
            print_api(message, logger=self.logger, logger_method='critical', traceback_string=True)
            # This will be treated as empty message - indicate that socket was closed and will be handled properly.
            pass
        except ConnectionResetError:
            message = "* Connection was forcibly closed by the client. Exiting..."
            print_api(message, logger=self.logger, logger_method='critical', traceback_string=True)
            # This will be treated as empty message - indicate that socket was closed and will be handled properly.
            pass
        except ssl.SSLError:
            message = "* Encountered SSL error on packet receive. Exiting..."
            print_api(message, logger=self.logger, logger_method='critical', traceback_string=True)
            # This will be treated as empty message - indicate that socket was closed and will be handled properly.
            pass

        if not class_data:
            self.logger.info("Empty message received, socket closed on the other side.")

        return class_data

    # Function to receive message
    def socket_receive_message_full(self):
        # Setting timeout for the client to receive connections, since there is no way to know when the message has
        # ended and the message is longer than the receiving buffer.
        # So we need to set the timeout for the client socket.
        # If you set "timeout" on the listening main socket, it is not inherited to the child socket when client
        # connected, so you need to set it for the new socket as well.
        # Each function need to set the timeout independently
        self.ssl_socket.settimeout(self.socket_timeout)
        # variable that is responsible to retry over the same receive session if packet is less than buffer
        partial_data_received: bool = False

        # Define the variable that is going to aggregate the whole data received
        class_data: bytearray = bytearray()
        # Define the variable that will be responsible for receive buffer
        class_data_received: bytes = bytes()

        # Infinite loop to accept data from the client
        while True:
            # SocketTimeout creates an exception that we need to handle with try and except.
            try:
                # The variable needs to be defined before receiving the socket data or else you will get an error
                # - variable not defined.
                # function_data_received: bytearray = bytearray()
                # Receiving data from the socket with "recv" method, while 1024 byte is a buffer size for the data.
                # "decode()" method converts byte message to string.
                class_data_received: bytes = self.socket_receive_message_buffer()
            # If there is no byte data received from the client and also the full message is not empty, then the loop
            # needs to break, since it is the last message that was received from the client
            except TimeoutError:
                if partial_data_received:
                    self.logger.info(f"Timed out after {self.socket_timeout} seconds - no more packets. "
                                     f"Passing current request of total {len(class_data)} bytes down the network chain")
                    # Pass the exception
                    pass
                    # Break the while loop, since we already have the request
                    break
                else:
                    self.logger.info(
                        # Dividing number of seconds by 60 to get minutes
                        f"{self.socket_timeout/60} minutes timeout reached on 'socket.recv()' - no data received from "
                        f"{self.class_client_address}:{self.class_client_local_port}. Still waiting...")
                    # Pass the exception
                    pass
                    # Changing the socket timeout back to none since receiving operation has been finished.
                    self.ssl_socket.settimeout(None)
                    # Continue to the next iteration inside while
                    continue

            # And if the message received is not empty then aggregate it to the main "data received" variable
            if class_data_received:
                class_data.extend(class_data_received)

                self.logger.info(f"Received packet with {len(class_data_received)} bytes. "
                                 f"Current aggregated request of total: {len(class_data)} bytes")

                # If the first received session is less than the buffer size, then the full message was received
                if len(class_data_received) < self.buffer_size_receive:
                    # Since we already received some data from the other side, the retried variable will be true
                    partial_data_received = True
                    self.logger.info(f"Receiving the buffer again...")

                    # In this case the socket timeout will be 2 seconds to wait for more packets.
                    # If there are no more packets, receiver will end its activity and pass the message to
                    # the rest of the components in the network chain
                    if self.socket_timeout != 0.5:
                        self.socket_timeout = 0.5
                        self.ssl_socket.settimeout(self.socket_timeout)
                        self.logger.info(f"Timeout changed to {self.socket_timeout} seconds")

                    # Continue to the next receive on the socket
                    continue
            else:
                if class_data:
                    self.logger.info(f"Since there's request received from the client of total {len(class_data)} "
                                     f"bytes, we'll first process it, and when the receiver will ask for data from "
                                     f"client in the next cycle - empty message will be received again, and current "
                                     f"socket will be finally closed.")
                break

        return class_data

    # noinspection PyBroadException
    def receive(self):
        # Getting client address from the socket
        self.class_client_address = self.ssl_socket.getpeername()[0]
        # Getting client Local port from the socket
        self.class_client_local_port = self.ssl_socket.getpeername()[1]

        # Receiving data from the socket and closing the socket if send is finished.
        self.logger.info(f"Waiting for data from {self.class_client_address}:{self.class_client_local_port}")
        function_client_data: bytearray = self.socket_receive_message_full()

        if function_client_data:
            # Put only 100 characters to the log, since we record the message any way in full - later.
            self.logger.info(f"Received: {function_client_data[0: 100]}...")

        return function_client_data

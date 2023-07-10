import ssl
import datetime

from . import base
from ...print_api import print_api


def accept_connection(socket_object, statistics, sni_queue, process_name_queue, **kwargs):
    client_socket = None
    client_address_tuple: tuple = tuple()
    message = str()

    try:
        # "accept()" bloc script I/O calls until receives network connection. When client connects "accept()"
        # returns client socket and client address. Non-blocking mode is supported with "setblocking()", but you
        # need to change your application accordingly to handle this.
        # The client socket will contain the address and the port.
        # Since the client socket is thrown each time to a thread function, it can be overwritten in the main loop
        # and thrown to the function again. Accept creates new socket each time it is being called on the main
        # socket.
        # "accept()" method of the "ssl.SSLSocket" object returns another "ssl.SSLSocket" object and not the
        # regular socket
        client_socket, client_address_tuple = socket_object.accept()

    # Each exception that calls 'service_name_from_sni' variables has a try on calling that variable.
    # If it is non-existent, then logger function that doesn't have this variable printed will be used.
    # After that second exception will be "pass"-ed. This is an exception inside an exception handling.
    # Looks like was introduced in Python 3 in PEP 3134.
    except ConnectionAbortedError:
        message = f"Socket Accept: {sni_queue.queue}:{socket_object.getsockname()[1]}: " \
                  f"* Established connection was aborted by software on the host..."
        print_api(message, logger_method='error', traceback_string=True, oneline=True, **kwargs)
        pass
    except ConnectionResetError:
        message = f"Socket Accept: {sni_queue.queue}:{socket_object.getsockname()[1]}: " \
                  f"* An existing connection was forcibly closed by the remote host..."
        print_api(message, logger_method='error', traceback_string=True, oneline=True, **kwargs)
        pass
    except ssl.SSLEOFError as e:
        # A subclass of SSLError raised when the SSL connection has been terminated abruptly. Generally, you
        # shouldn't try to reuse the underlying transport when this error is encountered.
        # https://docs.python.org/3/library/ssl.html#ssl.SSLEOFError
        # Nothing to do with it.

        message = f"ssl.SSLEOFError: {e}"
        try:
            message = f"Socket Accept: {sni_queue.queue}:{socket_object.getsockname()[1]}: {message}"
            print_api(message, logger_method='error', **kwargs)
        except Exception:
            message = f"Socket Accept: port {socket_object.getsockname()[1]}: {message}"
            print_api(message, logger_method='error', traceback_string=True, oneline=True, **kwargs)
            pass
        pass
    except ssl.SSLZeroReturnError as e:
        message = f"ssl.SSLZeroReturnError: {e}"
        try:
            message = f"Socket Accept: {sni_queue.queue}:{socket_object.getsockname()[1]}: {message}"
            print_api(message, logger_method='error', **kwargs)
        except Exception:
            message = f"Socket Accept: port {socket_object.getsockname()[1]}: {message}"
            print_api(message, logger_method='error', traceback_string=True, oneline=True, **kwargs)
            pass
        pass
    except ssl.SSLError as exception_object:
        # Getting the exact reason of "ssl.SSLError"
        if exception_object.reason == "HTTP_REQUEST":
            message = f"Socket Accept: HTTP Request on SSL Socket: {base.get_source_destination(socket_object)}"
            print_api(message, logger_method='error', traceback_string=True, oneline=True, **kwargs)
        elif exception_object.reason == "TSV1_ALERT_UNKNOWN_CA":
            message = f"Socket Accept: Check CA certificate on the client " \
                      f"{base.get_source_destination(socket_object)}"
            print_api(message, logger_method='error', traceback_string=True, oneline=True, **kwargs)
        # elif exception_object.reason == "SSLV3_ALERT_CERTIFICATE_UNKNOWN":
        #     message = f"ssl.SSLError:{exception_object}"
        #     message = f"Socket Accept: {sni_queue.queue}:{socket_object.getsockname()[1]}: {message}"
        #     print_api(message, logger=self.logger, logger_method='error', traceback_string=True, oneline=True)
        # elif exception_object.reason == "NO_SHARED_CIPHER":
        #     message = f"ssl.SSLError:{exception_object}"
        #     message = f"Socket Accept: {sni_queue.queue}:{socket_object.getsockname()[1]}: {message}"
        #     print_api(message, logger=self.logger, logger_method='error', traceback_string=True, oneline=True)
        else:
            # Not all requests have the server name passed through Client Hello.
            # If it is not passed an error of undefined variable will be raised.
            # So, we'll check if the variable as a string is in the "locals()" variable pool.
            # Alternatively we can check if the variable is in the "global()" and then pull it from there.

            message = "SSLError on accept. Not documented..."
            print_api(message, logger_method='error', **kwargs)
            # try:
            #     message = f"Socket Accept: {sni_queue.queue}:{socket_object.getsockname()[1]}: {message}"
            #     print_api(message, logger=self.logger, logger_method='error', traceback_string=True, oneline=True)
            # except Exception:
            #     message = f"Socket Accept: port {socket_object.getsockname()[1]}: {message}"
            #     print_api(message, logger=self.logger, logger_method='error', traceback_string=True, oneline=True)
            # pass

            message = f'ssl.SSLError:{exception_object}'
            message = f"Socket Accept: {sni_queue.queue}:{socket_object.getsockname()[1]}: {message}"
            print_api(message, logger_method='error', **kwargs)
        pass
    except FileNotFoundError:
        message = "'SSLSocket.accept()' crashed: 'FileNotFoundError'. Some problem with SSL during Handshake - " \
                  "Could be certificate, client, or server."
        message = f"Socket Accept: {sni_queue.queue}:{socket_object.getsockname()[1]}: {message}"
        print_api(message, logger_method='error', traceback_string=True, oneline=True, **kwargs)
        # except Exception:
        #     message = f"Socket Accept: port {socket_object.getsockname()[1]}: {message}"
        #     print_api(message, logger=self.logger, logger_method='error', traceback_string=True, oneline=True)
        #     pass
        pass
    except Exception:
        message = "Undocumented exception on accept."
        message = f"Socket Accept: {sni_queue.queue}:{socket_object.getsockname()[1]}: {message}"
        print_api(message, logger_method='error', traceback_string=True, oneline=True, **kwargs)
        pass
    # After all executions tested, this is what will be executed.
    finally:
        # If 'message' is not defined, it means there was no execution and there is no need for statistics.
        try:
            statistics_dict = {
                'request_time_sent': datetime.datetime.now(),
                'host': sni_queue.queue,
                'error': message
            }

            statistics.info(
                f"{statistics_dict['request_time_sent']},"
                f"{statistics_dict['host']},"
                f",,,,,,"
                f"\"{process_name_queue.queue}\","
                f"{statistics_dict['error']}"
            )
        except UnboundLocalError:
            pass
        except Exception:
            message = "Undocumented exception after accept on building statistics."
            print_api(message, logger_method='error', traceback_string=True, oneline=True, **kwargs)
            pass

    return client_socket, client_address_tuple

import ssl
import functools

from . import base
from ...print_api import print_api
from ...inspect_wrapper import get_target_function_default_args_and_combine_with_current


def connection_exception_decorator(function_name):
    @functools.wraps(function_name)
    def wrapper_handle_connection_exceptions(*args, **kwargs):
        # Put 'args' into 'kwargs' with appropriate key.
        # args, kwargs = put_args_to_kwargs(function_name, *args, **kwargs)
        args, kwargs = get_target_function_default_args_and_combine_with_current(function_name, *args, **kwargs)

        wrapper_handle_connection_exceptions.message = None
        listen_ipv4, port = kwargs['socket_object'].getsockname()

        domain_from_dns_server = kwargs['domain_from_dns_server']
        if not domain_from_dns_server:
            # If the domain is not passed, we will use the TCP data.
            # This is needed for the decorator to work properly.
            domain_from_dns_server = listen_ipv4

        try:
            # Since our 'kwargs' has already all the needed arguments, we don't need 'args'.
            return function_name(**kwargs)
            # Each exception that calls 'service_name_from_sni' variables has a try on calling that variable.
            # If it is non-existent, then logger function that doesn't have this variable printed will be used.
            # After that second exception will be "pass"-ed. This is an exception inside an exception handling.
            # Looks like was introduced in Python 3 in PEP 3134.
        except ConnectionAbortedError:
            message = f"Socket Accept: {domain_from_dns_server}:{port}: " \
                      f"* Established connection was aborted by software on the host..."
            wrapper_handle_connection_exceptions.message = message
            print_api(message, logger_method='error', traceback_string=True, oneline=True, **kwargs['print_kwargs'])
        except ConnectionResetError:
            message = f"Socket Accept: {domain_from_dns_server}:{port}: " \
                      f"* An existing connection was forcibly closed by the remote host..."
            wrapper_handle_connection_exceptions.message = message
            print_api(message, logger_method='error', traceback_string=True, oneline=True, **kwargs['print_kwargs'])
        except ssl.SSLEOFError as e:
            # A subclass of SSLError raised when the SSL connection has been terminated abruptly. Generally, you
            # shouldn't try to reuse the underlying transport when this error is encountered.
            # https://docs.python.org/3/library/ssl.html#ssl.SSLEOFError
            # Nothing to do with it.

            message = f"ssl.SSLEOFError: {e}"
            wrapper_handle_connection_exceptions.message = message
            try:
                message = \
                    f"Socket Accept: {domain_from_dns_server}:{port}: {message}"
                wrapper_handle_connection_exceptions.message = message
                print_api(message, error_type=True, logger_method='error', oneline=True, **kwargs['print_kwargs'])
            except Exception as e:
                _ = e
                message = f"Socket Accept: port {port}: {message}"
                wrapper_handle_connection_exceptions.message = message
                print_api(message, logger_method='error', traceback_string=True, oneline=True, **kwargs['print_kwargs'])
                pass
            pass
        except ssl.SSLZeroReturnError as e:
            message = f"ssl.SSLZeroReturnError: {e}"
            wrapper_handle_connection_exceptions.message = message
            try:
                message = \
                    f"Socket Accept: {domain_from_dns_server}:{port}: {message}"
                wrapper_handle_connection_exceptions.message = message
                print_api(message, logger_method='error', oneline=True, **kwargs['print_kwargs'])
            except Exception as e:
                _ = e
                message = f"Socket Accept: port {port}: {message}"
                wrapper_handle_connection_exceptions.message = message
                print_api(message, logger_method='error', traceback_string=True, oneline=True, **kwargs['print_kwargs'])
                pass
            pass
        except ssl.SSLError as exception_object:
            # Getting the exact reason of "ssl.SSLError"
            if exception_object.reason == "HTTP_REQUEST":
                message = f"Socket Accept: HTTP Request on SSL Socket: " \
                          f"{base.get_source_destination(kwargs['socket_object'])}"
                wrapper_handle_connection_exceptions.message = message
                print_api(message, logger_method='error', traceback_string=True, oneline=True, **kwargs['print_kwargs'])
            elif exception_object.reason == "TSV1_ALERT_UNKNOWN_CA":
                message = f"Socket Accept: Check CA certificate on the client " \
                          f"{base.get_source_destination(kwargs['socket_object'])}"
                wrapper_handle_connection_exceptions.message = message
                print_api(message, logger_method='error', traceback_string=True, oneline=True, **kwargs['print_kwargs'])
            else:
                # Not all requests have the server name passed through Client Hello.
                # If it is not passed an error of undefined variable will be raised.
                # So, we'll check if the variable as a string is in the "locals()" variable pool.
                # Alternatively we can check if the variable is in the "global()" and then pull it from there.

                message = "SSLError on accept. Not documented..."
                wrapper_handle_connection_exceptions.message = message
                print_api(message, logger_method='error', oneline=True, **kwargs['print_kwargs'])

                message = f'ssl.SSLError:{exception_object}'
                wrapper_handle_connection_exceptions.message = message
                message = \
                    f"Socket Accept: {domain_from_dns_server}:{port}: {message}"
                wrapper_handle_connection_exceptions.message = message
                print_api(message, logger_method='error', oneline=True, **kwargs['print_kwargs'])
            pass
        except FileNotFoundError:
            message = "'SSLSocket.accept()' crashed: 'FileNotFoundError'. Some problem with SSL during Handshake - " \
                      "Could be certificate, client, or server."
            message = f"Socket Accept: {domain_from_dns_server}:{port}: {message}"
            wrapper_handle_connection_exceptions.message = message
            print_api(message, logger_method='error', traceback_string=True, oneline=True, **kwargs['print_kwargs'])
            pass
        except Exception as e:
            _ = e
            message = "Undocumented exception on accept."
            message = f"Socket Accept: {domain_from_dns_server}:{port}: {message}"
            wrapper_handle_connection_exceptions.message = message
            print_api(message, logger_method='error', traceback_string=True, oneline=True, **kwargs['print_kwargs'])
            pass

    wrapper_handle_connection_exceptions.message = None
    return wrapper_handle_connection_exceptions

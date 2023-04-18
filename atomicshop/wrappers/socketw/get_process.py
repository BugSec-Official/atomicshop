# Needed to redirect output from console to logger on LOCALHOST process command line harvesting.
import io
from contextlib import redirect_stdout

from ...ssh_remote import SSHRemote

import psutil


def get_process_commandline(client_ip: str, username: str, password: str, script_string: str, logger):
    execution_output = None
    execution_error = None

    # Checking if we're on localhost. If not, we'll execute SSH connection to get calling process name.
    if client_ip != "127.0.0.1":
        # Tried using paramiko SSH concurrently within threads, but with bigger loads it just breaks.
        # So, better using it separately for each thread.

        logger.info(f"Initializing SSH connection to [{client_ip}]")
        # Initializing SSHRemote class.
        current_ssh_client = SSHRemote(ip_address=client_ip,
                                       username=username,
                                       password=password)

        execution_output, execution_error = current_ssh_client.connect_get_client_commandline(script_string)
    # Else, if we're on localhost, then execute the script directly without SSH.
    else:
        logger.info("Executing LOCALHOST command to get the calling process.")
        # Getting the redirection from console print, since that what the 'script_string' does.
        with io.StringIO() as buffer, redirect_stdout(buffer):
            # Executing the script with print to console.
            try:
                exec(script_string)
            except ModuleNotFoundError as function_exception_object:
                execution_error = f"Module not installed: {function_exception_object}"
                logger.error_exception_oneliner(execution_error)
                pass
            except psutil.AccessDenied:
                execution_error = f"Access Denied for 'psutil' to read system process command line. " \
                                  f"Run script with Admin Rights."
                logger.error_exception_oneliner(execution_error)
                pass
            except Exception as function_exception_object:
                execution_error = function_exception_object
                logger.error_exception_oneliner(
                    "There was undocumented exception in localhost script execution.")
                pass

            if not execution_error:
                # Reading the buffer.
                execution_output = buffer.getvalue()

    # This section is generic for both remote SSH and localhost executions of the script.
    process_name = get_commandline_and_error(execution_output, execution_error, logger)

    return process_name


def get_commandline_and_error(execution_output, execution_error, logger):
    # If there was known error on localhost / known error on remote or any kind of error on remote, it was
    # already logged, so we'll just put the error into 'process_name'.
    if execution_error:
        process_name = execution_error
        logger.error(f"Error During Command Execution: {process_name}")
    # If there wasn't any error of above types, then we can put the output from either local or remote script
    # execution into 'process_name' and log it / output to console.
    else:
        # If the output that was returned is not empty.
        if execution_output:
            # Replacing '\r\n' escape lines with string, so that the line will not be escaped in logs.
            if '\r\n' in execution_output:
                execution_output = execution_output.replace('\r\n', '')
            elif '\n' in execution_output:
                execution_output = execution_output.replace('\n', '')

            process_name = execution_output
            logger.info(f"Client Process Command Line: {process_name}")
        # Else if the script output came back empty.
        else:
            process_name = "Client Process Command Line came back empty after script execution."
            logger.error(process_name)

    return process_name

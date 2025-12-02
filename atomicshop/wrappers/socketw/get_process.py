import logging

from . import base
from ...print_api import print_api
from ...ssh_remote import SSHRemote
from ... import package_mains_processor


GET_LOCALHOST_FUNCTION_NAME = 'find_cmdline_by_port'


class GetCommandLine:
    def __init__(
            self,
            client_socket=None,
            package_processor: package_mains_processor.PackageMainsProcessor = None,
            ssh_client: SSHRemote = None,
            logger: logging.Logger = None
    ):
        self.client_socket = client_socket
        self.package_processor: package_mains_processor.PackageMainsProcessor = package_processor
        self.ssh_client: SSHRemote = ssh_client
        self.logger: logging.Logger = logger

    def get_process_name(self, print_kwargs: dict = None):
        # Get client ip and the source port.
        client_ip, client_port = base.get_source_address_from_socket(self.client_socket)

        # Checking if we're on localhost. If not, we'll execute SSH connection to get calling process name.
        if client_ip not in base.THIS_DEVICE_IP_LIST:
            # Tried using paramiko SSH concurrently within threads, but with bigger loads it just breaks.
            # So, better using it separately for each thread.

            print_api(f"Initializing SSH connection to [{client_ip}]", **print_kwargs)

            script_string: str = self.package_processor.read_script_file_to_string()

            execution_output, execution_error = self.ssh_client.connect_get_client_commandline(port=client_port, script_string=script_string)
        # Else, if we're on localhost, then execute the script directly without SSH.
        else:
            print_api(f"Executing LOCALHOST command to get the calling process.", **print_kwargs)
            # execution_output, execution_error, rc = self.package_processor.execute_script_with_subprocess(arguments=[str(client_port)])
            execution_output = self.package_processor.execute_script_file(
                function_name=GET_LOCALHOST_FUNCTION_NAME, args=(client_port,))
            execution_error = None

        # This section is generic for both remote SSH and localhost executions of the script.
        process_name = self.get_commandline_and_error(execution_output, execution_error, print_kwargs=print_kwargs)

        return process_name

    @staticmethod
    def get_commandline_and_error(
            execution_output,
            execution_error,
            print_kwargs: dict = None
    ):
        # If there was known error on localhost / known error on remote or any kind of error on remote, it was
        # already logged, so we'll just put the error into 'process_name'.
        if execution_error:
            process_name = execution_error
            print_api(
                f"Error During Command Execution: {process_name}", error_type=True,
                logger_method='error', **(print_kwargs or {}))
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
                print_api(f"Client Process Command Line: {process_name}", **(print_kwargs or {}))
            # Else if the script output came back empty.
            else:
                process_name = ''
                message = "Client Process Command Line came back empty after script execution."
                print_api(message, error_type=True, logger_method='error', **(print_kwargs or {}))

        return process_name

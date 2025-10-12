import sys
import base64
import logging
from pathlib import Path

try:
    import paramiko
except ImportError as exception_object:
    print(f"Library missing: {exception_object.name}. Install by executing: pip install paramiko")
    sys.exit()

from .print_api import print_api
from .wrappers.loggingw import loggingw
from .wrappers.socketw import base


class SSHRemote:
    """
    Tried using paramiko SSH concurrently within threads, but with bigger loads it just breaks.
    So, better initializing it separately for each thread. Slower, but more reliable.

    If still needed to use one connection for all threads:
        # Basic imports.
        import sys

        # Defining variables.
        address_to_ssh_dictionary: dict = dict()

        def thread_worker_main(function_client_socket_object: ssl.SSLSocket):
            # Getting globals.
            global address_to_ssh_dictionary

            # Defining local variables.
            execution_output = None
            execution_error = None

            # Checking if we're on localhost. If not, we'll execute SSH connection to get calling process name.
            if client_message.client_ip != "127.0.0.1":
                network.logger.info(f"Assigning SSH connection to [{client_message.client_ip}]")
                current_ssh_client = address_to_ssh_dictionary[client_message.client_ip]
                network.logger.info(f"Assigned SSH : {current_ssh_client}")

                network.logger.info("Executing SSH command to get the calling process.")
                execution_output, execution_error = current_ssh_client.remote_execution_python(script_string)

                # In case SSH was reconnected during command execution, we need to reassign it in the dictionary.
                address_to_ssh_dictionary[client_message.client_ip] = current_ssh_client

        def main():
            # Getting globals.
            global address_to_ssh_dictionary

            # Wait from any connection on "accept()"
            client_socket, client_address = accept_connection(main_ssl_socket_object)
            if client_socket:
                client_socket: ssl.SSLSocket
                client_address: tuple

                # 'client_address[0]' is the IP address of the connected client.
                # So if the address is not in the dictionary, we'll add it with SSH connection. So, we can connect there
                # during thread network chain and execute scripts. Also, if we're in localhost environment, we don't
                # need this.
                if client_address[0] != "127.0.0.1" and client_address[0] not in address_to_ssh_dictionary:
                    system.logger.info(
                        f"Client IP [{client_address[0]}] is not in the SSH connection dictionary. Connecting.")
                    # Initializing SSHRemote class.
                    ssh_client = \
                        SSHRemote(
                            ip_address=client_address[0], username=client_os_username, password=client_os_password)
                    # Making actual SSH Connection to the computer.
                    ssh_connection_error = ssh_client.connect()
                    address_to_ssh_dictionary[client_address[0]] = ssh_client
                    system.logger.info(f"Connected and added to dictionary for further usage.")

                # Creating thread for each socket
                thread_current = threading.Thread(target=thread_worker_main, args=(client_socket,))
                # Append to list of threads, so they can be "joined" later
                threads_list.append(thread_current)
                # Start the thread
                thread_current.start()

                listener.logger.info(f"Accepted connection, thread created {client_address}. Continue listening...")

        if __name__ == '__main__':
            # Execute when the module is not initialized from an import statement.
            sys.exit(main())

    """
    def __init__(
            self,
            ip_address: str,
            username: str,
            password: str,
            logger: logging.Logger = None
    ):
        self.ip_address: str = ip_address
        self.username: str = username
        self.password: str = password

        # Initializing paramiko SSHClient class
        self.ssh_client = paramiko.SSHClient()

        if logger:
            # Create child logger for the provided logger with the module's name.
            self.logger: logging.Logger = loggingw.get_logger_with_level(f'{logger.name}.{Path(__file__).stem}')
        else:
            self.logger: logging.Logger = logger

    def connect(self):
        error: str = str()

        # Get all local interfaces IPv4 addresses.
        local_interfaces_ipv4 = base.get_local_network_interfaces_ip_address("ipv4", True)
        # Check if the target IP address is in the list of local interfaces.
        if self.ip_address in local_interfaces_ipv4:
            # If it is, we don't need to connect to it via SSH, it means that we want to connect to ourselves.
            # Probably the target computer is a VM with NAT connection, should be bridged.
            error = f"SSHRemote: Target IP [{self.ip_address}] is one of the local computer network interfaces! " \
                    f"Probably the target computer is a VM with NAT connection, should be bridged connection."
            print_api(error, logger=self.logger, logger_method='error')
            return error

        # Since we're connecting within private network we don't actually care about security, so setting
        # the policy to Automatic instead of
        # ssh_client.load_system_host_keys()
        # If we won't set this we'll get an error of type
        # paramiko.ssh_exception.SSHException
        # with description of
        # Server 'address_goes_here' not found in known_hosts
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Executing SSH connection to client.
        self.ssh_client.connect(self.ip_address, username=self.username, password=self.password, timeout=60)

        return error

    def close(self):
        self.ssh_client.close()

    @staticmethod
    def check_console_output_for_errors(console_output_string: str):
        # Defining variables.
        function_result = None

        if 'The system cannot execute the specified program' in console_output_string:
            function_result = f"'The system cannot execute the specified program'. Probably python is not installed " \
                              f"or python installation path is not in PATH environment variable."
        elif "ModuleNotFoundError: No module named" in console_output_string:
            # Splitting the string to lines, so we can extract the exact line with library name.
            for line in console_output_string.splitlines():
                if "ModuleNotFoundError: No module named" in line:
                    function_result = f"Python library is not installed - {line}"
                    break

        return function_result

    def remote_execution(self, script_string: str) -> tuple[str, str]:
        output_result: str = str()
        error_result: str = str()

        # Execute the command over SSH remotely.
        # Don't put debugging break point over the next line in PyCharm. For some reason it gets stuck.
        # Put the point right after that.
        stdin, stdout, stderr = self.ssh_client.exec_command(command=script_string, timeout=30)

        # Reading the buffer of stdout.
        output_lines: list = stdout.readlines()
        # Reading the buffer of stderr.
        error_lines: list = stderr.readlines()

        # Joining error lines list to string if not empty.
        if error_lines:
            error_result: str = ''.join(error_lines)
        # Else, joining output lines to string.
        else:
            output_result = ''.join(output_lines)

        # Since they're "file-like" objects we need to close them after we finished using.
        stdin.close()
        stdout.close()
        stderr.close()

        return output_result, error_result

    def remote_execution_python(self, script_string: str):
        """
        Function to execute python script over SSH.

        Example:
                network.logger.info("Initializing SSH connection to get the calling process.")

                # Initializing SSHRemote class.
                ssh_client = SSHRemote(ip_address=client_message.client_ip, username=username, password=password)
                # Making actual SSH Connection to the computer.
                ssh_connection_error = ssh_client.connect()
                # If there's an exception / error during connection.
                if ssh_connection_error:
                    # Put the error in the process name value.
                    client_message.process_name = ssh_connection_error
                else:
                    # If no error, then initialize the variables for python script execution over SSH.
                    remote_output = remote_error = None

                    # Put source port variable inside the string script.
                    script_string: str = \
                        put_variable_into_string_script(ssh_script_port_by_process_string, client_message.source_port)

                    # Execute the python script on remote computer over SSH.
                    remote_output, remote_error = ssh_client.remote_execution_python(script_string)

                    # If there was an error during execution, put it in process name.
                    if remote_error:
                        client_message.process_name = remote_error
                    # If there was no error during execution, put the output of the ssh to process name.
                    else:
                        client_message.process_name = remote_output
                        network.logger.info(f"Remote SSH: Client executing Command Line: {client_message.process_name}")

        :param script_string: string representation of python script.
        :return: SSH console output, Error output
        """
        # Defining variables.
        error_result: str | None = None

        encoded_base64_string = base64.b64encode(script_string.encode('ascii'))
        command_string: str = fr'python -c "import base64;exec(base64.b64decode({encoded_base64_string}))"'

        # remote_output, remote_error = ssh_client.remote_execution('ipconfig')
        # remote_output, remote_error = ssh_client.remote_execution("python -c print('Hello')")
        # remote_output, remote_error = ssh_client.remote_execution("python -c import psutil")
        remote_output, remote_error = self.remote_execution(command_string)

        # If there was an error during remote execution
        if remote_error:
            # Check for known errors and return full error message.
            console_check = self.check_console_output_for_errors(remote_error)
            # If the message is known and didn't return empty.
            if console_check:
                # 'execution_error' variable will be that full error.
                error_result = console_check

        return remote_output, error_result

    def connect_get_client_commandline(self, script_string):
        # Defining locals.
        execution_output: str | None = None

        # Making actual SSH Connection to the computer.
        execution_error = self.connect()
        # if there was an error, try to connect again.
        if execution_error:
            self.logger.info("Retrying SSH Connection Initialization.")
            execution_error = self.connect()

        # If there was still an error, we won't be executing the script. And the error will be passed to
        # 'process_name'.
        if not execution_error:
            self.logger.info("Executing SSH command to acquire the calling process.")

            execution_output, execution_error = self.remote_execution_python(script_string)

            # Closing SSH connection at this stage.
            self.close()
            self.logger.info("Acquired. Closed SSH connection.")

        return execution_output, execution_error

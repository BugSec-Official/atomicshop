import sys
import base64
import socket

from .print_api import print_api
from .wrappers.loggingw import loggingw
from .wrappers.socketw import base


# External Libraries
try:
    import paramiko
except ImportError as exception_object:
    print(f"Library missing: {exception_object.name}. Install by executing: pip install paramiko")
    sys.exit()


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
    logger = loggingw.get_logger_with_level("network." + __name__.rpartition('.')[2])

    def __init__(self, ip_address: str, username: str, password: str):
        self.ip_address: str = ip_address
        self.username: str = username
        self.password: str = password

        # Initializing paramiko SSHClient class
        self.ssh_client = paramiko.SSHClient()

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
        try:
            # Executing SSH connection to client.
            self.ssh_client.connect(self.ip_address, username=self.username, password=self.password, timeout=60)
        # When port 22 is unreachable on the client.
        except paramiko.ssh_exception.NoValidConnectionsError as e:
            error = str(e)
            # Logging the error also. Since the process name isn't critical, we'll continue script execution.
            print_api(error, logger=self.logger, logger_method='error', traceback_string=True, oneline=True)
            pass
        except paramiko.ssh_exception.SSHException as e:
            error = str(e)
            # Logging the error also. Since the process name isn't critical, we'll continue script execution.
            print_api(error, logger=self.logger, logger_method='error', traceback_string=True, oneline=True)
            pass
        except ConnectionResetError:
            # Returning the error.
            error = "An existing connection was forcibly closed by the remote host."
            # Logging the error also. Since the process name isn't critical, we'll continue script execution.
            print_api(error, logger=self.logger, logger_method='error', traceback_string=True, oneline=True)
            pass
        except TimeoutError:
            # Returning the error.
            error = "Connection timed out."
            # Logging the error also. Since the process name isn't critical, we'll continue script execution.
            print_api(error, logger=self.logger, logger_method='error', traceback_string=True, oneline=True)
            pass

        return error

    def close(self):
        self.ssh_client.close()

    def exec_command_with_error_handling(self, script_string: str):
        # Defining variables.
        stdin = None
        stdout = None
        stderr = None
        result_exception = None

        # Don't put debugging break point over the next line in PyCharm. For some reason it gets stuck.
        # Put the point right after that.
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command=script_string, timeout=30)
        except AttributeError as function_exception_object:
            if function_exception_object.name == "open_session":
                result_exception = "'SSHRemote().connect' wasn't executed."
                print_api(result_exception, logger=self.logger, logger_method='error', traceback_string=True, oneline=True)

                # Since getting Process name is not the main feature of the server, we can pass the exception
                pass
            else:
                result_exception = f"Couldn't execute script over SSH. Unknown yet exception with 'AttributeError' " \
                                   f"and name: {function_exception_object.name}"
                print_api(result_exception, logger=self.logger, logger_method='error', traceback_string=True, oneline=True)
                # Since getting Process name is not the main feature of the server, we can pass the exception
                pass
        except socket.error:
            result_exception = "Couldn't execute script over SSH. SSH socket closed."
            print_api(result_exception, logger=self.logger, logger_method='error', traceback_string=True, oneline=True)
            # Since getting Process name is not the main feature of the server, we can pass the exception
            pass
        except Exception:
            result_exception = "Couldn't execute script over SSH. Unknown yet exception."
            print_api(result_exception, logger=self.logger, logger_method='error', traceback_string=True, oneline=True)
            # Since getting Process name is not the main feature of the server, we can pass the exception
            pass

        return stdin, stdout, stderr, result_exception

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

    def remote_execution(self, script_string: str):
        # Defining variables.
        output_lines = None
        function_error = None
        stdin = None
        stdout = None
        stderr = None
        exec_exception = None

        # Execute the command over SSH remotely.
        stdin, stdout, stderr, exec_exception = self.exec_command_with_error_handling(script_string)
        # If exception was returned from execution.
        if exec_exception:
            self.logger.info("Trying to reconnect over SSH.")
            # Close existing SSH Connection.
            self.close()
            # And connect again.
            self.connect()
            self.logger.info("Reconnected. Trying to send the command one more time.")
            # Try to execute the command over SSH remotely again.
            stdin, stdout, stderr, exec_exception = self.exec_command_with_error_handling(script_string)
            # If there was an exception again.
            if exec_exception:
                # Populate the function_error variable that will be returned outside.
                function_error = exec_exception

        # If there was no exception executing the remote command.
        if not function_error:
            # Reading the buffer of stdout.
            output_lines = stdout.readlines()
            # Reading the buffer of stderr.
            function_error = stderr.readlines()

            # Joining error lines list to string if not empty.
            if function_error:
                function_error = ''.join(function_error)
            # Else, joining output lines to string.
            else:
                output_lines = ''.join(output_lines)

            # Since they're "file-like" objects we need to close them after we finished using.
            stdin.close()
            stdout.close()
            stderr.close()

        return output_lines, function_error

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
        function_return = None
        function_error = None

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
                function_error = console_check

        return remote_output, function_error

    def connect_get_client_commandline(self, script_string):
        # Defining locals.
        execution_output = None
        execution_error = None

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

            try:
                execution_output, execution_error = self.remote_execution_python(script_string)
            # Basically we don't care much about SSH exceptions. Just log them and pass to record.
            except Exception as function_exception_object:
                execution_error = function_exception_object
                print_api(execution_error, logger=self.logger, logger_method='error', traceback_string=True, oneline=True)
                pass

            # Closing SSH connection at this stage.
            self.close()
            self.logger.info("Acquired. Closed SSH connection.")

        return execution_output, execution_error

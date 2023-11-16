import functools
from typing import Union
import shlex
from subprocess import Popen, PIPE, STDOUT, CREATE_NEW_CONSOLE
import subprocess

from .print_api import print_api
from .inspect_wrapper import get_target_function_default_args_and_combine_with_current
from .basics.strings import match_pattern_against_string
from .process_poller import GetProcessList


def process_execution_decorator(function_name):
    @functools.wraps(function_name)
    def wrapper_process_execution_decorator(*args, **kwargs):
        # Put 'args' into 'kwargs' with appropriate key.
        # args, kwargs = put_args_to_kwargs(function_name, *args, **kwargs)
        args, kwargs = get_target_function_default_args_and_combine_with_current(function_name, *args, **kwargs)

        try:
            # print_api(message=f"Reading file: {kwargs['file_path']}", **kwargs)
            return function_name(**kwargs)
        # If the main command doesn't exist or cmd/bash can't execute it, 'FileNotFoundError' exception will raise.
        except FileNotFoundError:
            # The first entry in the list is the executable itself that is missing. If the main executable has files
            # as input or output, you will not get python exception, rather you will get error message from the process.
            print_api(f'Executable non-existent: [{kwargs["cmd"][0]}]', color="red", error_type=True, **kwargs)
            return None

    return wrapper_process_execution_decorator





@process_execution_decorator
def execute_with_live_output(
        cmd: Union[list, str],
        print_empty_lines: bool = False,
        verbose: bool = False,
        output_strings: list = None,
        wsl: bool = False,
        **kwargs
) -> list:
    """
    There are processes that print live, new lines of output. We need to make sure that the script does the same.
    'subprocess.Popen' in its default configuration waits for the process to finish, before you can get the output.
    It's problematic in our case, since we need real time output.
    If execution was successful, return True, if not - False.

    :param cmd: List of commands. Can be string (full command line), that will be converted to list.
    :param print_empty_lines: Boolean that sets if the program should print empty lines or not.
        In case of True, 'print_output' setting should be 'Ture' also.
    :param verbose: boolean.
        'True': Print all output lines of the process.
        'False': Don't print any lines of output.
    :param output_strings: list, of strings. If output line contains any of the strings it will be outputted to console.
    :param wsl: boolean, that sets if the command is executed with WSL.
    :return: Boolean, If execution was successful, return True, if not - False.
    """

    cmd = _execution_parameters_processing(cmd, wsl)

    # Needed imports:
    # from subprocess import Popen, PIPE, STDOUT

    # Properties:
    # stdout=PIPE: Pipe all the regular 'stdout' of the console to the 'stdout' variable.
    # stderr=STDOUT: 'stderr' is responsible for output of any errors that the process might have.
    #   Basically, anything that has any non-zero exit code. 'STDOUT' option of this property will
    #   output all the error output to 'stdout' variable as well. This way when you output new lines
    #   in a loop, you don't need to worry about checking 'stderr' buffer.
    # text=True: by default the output is binary, this option sets the output to text / string.
    with Popen(cmd, stdout=PIPE, stderr=STDOUT, bufsize=1, text=True) as process:
        # We'll count the number of lines from 'process.stdout'.
        counter: int = 0
        # And also get list of all the lines.
        lines_list: list = list()
        for line in process.stdout:
            # Since each line ends with '\n' we will get double space on print function.
            # Off-course we also can also fix it with "print(line, end='')", so each print end will not skip line.
            if line.endswith("\n"):
                line = line.removesuffix("\n")

            if not print_empty_lines and line == '':
                continue

            if verbose:
                print_api(line, **kwargs)
            elif output_strings:
                for single_string in output_strings:
                    if single_string in line:
                        print_api(line, **kwargs)

            counter += 1
            lines_list.append(line)

        # Another method.
        # while True:
        #     # Read line from stdout, break if EOF reached, append line to output
        #     line = process.stdout.readline()
        #     if line == "":
        #         break
        #     print(line)

        # If there are no lines, it means there was no output from the proces.
        if counter == 0:
            no_output_string: str = 'No output.'

            print_api(no_output_string, **kwargs)

            lines_list.append(no_output_string)

    return lines_list


@process_execution_decorator
def execute_in_new_window(
        cmd: Union[list, str],
        shell: bool = False,
        wsl: bool = False,
        **kwargs
):
    """
    The function executes list of arguments 'cmd' including the process in a new terminal window.
    Non-Blocking.

    :param cmd: List of commands. Can be string (full command line), that will be converted to list.
    :param shell: boolean, that sets if cmd will be used to execute the command.
    :param wsl: boolean, that sets if the command is executed with WSL.
    :return: Popen object of opened process.
    """

    cmd = _execution_parameters_processing(cmd, wsl)

    executed_process = Popen(cmd, shell=shell, creationflags=CREATE_NEW_CONSOLE)
    return executed_process


def execute_script_ubuntu(script: str, check: bool = True, shell: bool = False):
    """
    The function executes terminal bash script in Ubuntu.
    :param script: string, script to execute.
    :param check: check=True: When this is set, if the command executed with subprocess.run() returns a non-zero
        exit status (which usually indicates an error), a subprocess.CalledProcessError exception will be raised.
        This is useful for error handling, as it lets you know if something went wrong with the command's execution.
        Without check=True, subprocess.run() will not raise an exception for non-zero exit codes, and you would have
        to check the return code manually if you want to handle errors.
    :param shell: shell=True: This parameter allows you to pass a string command
        (just as you would type it in the shell) directly to subprocess.run().
        When shell=True, the specified command will be executed through the shell, giving you access to shell features
        like shell pipes, filename wildcards, environment variable expansion, and expansion of ~ to a user's
        home directory. However, using shell=True can be a security hazard, especially when combining it with
        untrusted input, as it makes the code susceptible to shell injection attacks.
        It's generally safer to use shell=False (the default) and pass your arguments as a list of strings.
        shell=True allows you to execute complex shell commands, including those with multiple statements,
        directly in Python, just as you would in a bash script.
        'cd' is shell-specific functionality.
        Without shell=True, the Python subprocess module would not understand the command "cd <directory>" as it's
        not an executable but a shell built-in command.
    :return: None if execution was successful, subprocess.CalledProcessError string if not.
    """
    try:
        subprocess.run(script, check=check, shell=shell, executable='/bin/bash')
        return None
    except subprocess.CalledProcessError as e:
        return e


def _execution_parameters_processing(cmd: Union[list, str], wsl: bool = False):
    """
    The function processes the execution parameters for the 'execute_' functions.

    :param cmd: List of commands. Can be string (full command line), that will be converted to list.
    :param wsl: boolean, that sets if the command is executed with WSL.
    :return: list, of commands, that will be passed to 'subprocess.Popen' function.
    """

    if isinstance(cmd, str):
        cmd = shlex.split(cmd)

    if wsl:
        cmd = ['wsl'] + cmd

    return cmd


def safe_terminate(popen_process: Popen):
    # Terminate the process with 'Popen' api.
    popen_process.terminate()
    # And wait for it to close.
    popen_process.wait()


def match_pattern_against_running_processes_cmdlines(pattern: str, first: bool = False, prefix_suffix: bool = False):
    """
    The function matches specified string pattern including wildcards against all the currently running processes'
    command lines.

    :param pattern: string, the pattern that we will search in the command line list of currently running processes.
    :param first: boolean, that will set if first pattern match found the iteration will stop, or we will return
        the list of all command lines that contain the pattern.
    :param prefix_suffix: boolean. Check the description in 'match_pattern_against_string' function.
    """

    # Get the list of all the currently running processes.
    get_process_list = GetProcessList(get_method='pywin32', connect_on_init=True)
    processes = get_process_list.get_processes(as_dict=False)

    # Iterate through all the current process, while fetching executable file 'name' and the command line.
    # Name is always populated, while command line is not.
    matched_cmdlines: list = list()
    for process in processes:
        # Check if command line isn't empty and that string pattern is matched against command line.
        if process['cmdline'] and \
                match_pattern_against_string(pattern, process['cmdline'], prefix_suffix):
            matched_cmdlines.append(process['cmdline'])
            # If 'first' was set to 'True' we will stop, since we found the first match.
            if first:
                break

    return matched_cmdlines

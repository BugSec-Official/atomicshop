# importing the psutil library to get the source ports and get the process full command line from it.
import psutil
# 'psutil.Process(connection.pid).cmdline()' returns list of full command line parts, it is needed to reassemble
# these parts to regular command line string.
import shlex

# 'input_variable' will be string exchanged in the real script. It is the first line, so it won't take time to find the
# line for the main script.
# noinspection PyUnresolvedReferences
source_port = exchange_input_variable

# Iterating through all the connections on the computer.
for connection in psutil.net_connections():
    # 'connection.laddr' is a tuple consisting of IPv4 address [0] and the port [1].
    if connection.laddr[1] == source_port:
        # Get the command line from the connection PID.
        command_line = psutil.Process(connection.pid).cmdline()
        # Command line object is returned as list of parameters. We need 'shlex.join' to join the iterables
        # to regular, readable string.
        result = shlex.join(command_line)
        # If the result is still a PID, we'll try to get process name.
        if result.isnumeric():
            # Get the process name from the connection PID.
            result = psutil.Process(connection.pid).name()
        print(result)
        # Break the loop, when first match is found.
        break

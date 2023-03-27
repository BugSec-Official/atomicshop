# importing the psutil library to get the source ports and get the process full command line from it.
import psutil
# 'psutil.Process(connection.pid).cmdline()' returns list of full command line parts, it is needed to reassemble
# these parts to regular command line string.
import shlex


# User defined exception.
class StopAllIterations(Exception):
    pass


# 'input_variable' will be string exchanged in the real script. It is the first line, so it won't take time to find the
# line for the main script.
# noinspection PyUnresolvedReferences
remote_ipv4_list = exchange_input_variable


try:
    # for iteration in range(100):
    # Iterating through all the connections on the computer.
    for connection in psutil.net_connections(kind='all'):
        # 'connection.raddr' is a tuple consisting of IPv4 address [0] and the port [1].
        # Sometimes, if there's no remote address, "raddr" will be empty and since it's a tuple, we need to check that
        # before getting the first [0] index.
        if connection.raddr:
            for address in remote_ipv4_list:
                if connection.raddr[0] == address:
                    # Get the command line from the connection PID.
                    command_line = psutil.Process(connection.pid).cmdline()
                    # Command line object is returned as list of parameters. We need 'shlex.join' to join the iterables
                    # to regular, readable string.
                    print(shlex.join(command_line))
                    # Break the loops, when first match is found.
                    raise StopAllIterations
except StopAllIterations:
    pass

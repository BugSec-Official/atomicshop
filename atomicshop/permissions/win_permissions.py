import subprocess


def unblock_file_windows(file_path):
    """
    Unblock a file on Windows. This is used to unblock files downloaded from the internet.
    When you Right-click then navigate to Properties, you will see the Unblock checkbox.
    :param file_path:
    :return:
    """
    try:
        subprocess.run(["powershell", "-Command", f"Unblock-File -Path '{file_path}'"], check=True)
        print(f"Successfully unblocked the file: {file_path}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to unblock the file: {file_path}\nError: {e}")


def get_command_to_run_as_admin_windows(command: str) -> str:
    """
    Function returns the command to run a command as administrator on Windows.
    NOTE: When you run something this way, the parent will be the powershell.exe process.
        If you need a status result directly of the executed command, you need to use subprocess.run() instead.

    :param command: str, command to run.
    :return: str, command to run as administrator.
    """

    executable = command.split()[0]
    command = (
        f"powershell -Command "
        f"\"Start-Process {executable} -ArgumentList '{' '.join(command.split()[1:])}' -Verb RunAs\"")

    return command

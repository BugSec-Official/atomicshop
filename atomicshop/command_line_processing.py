# v1.0.0 - 17.02.2023 14:50
import shlex


def split_cmd_to_list(command_string: str) -> list:
    """
    Function gets command string and returns arguments divided list.
    Example:
        ffmpeg.exe -i "c:\test folder\file.mp3" "c:\test folder\file.wav" -y
    Returns:
        ['ffmpeg.exe', '-i', 'c:\test folder\file.mp3', 'c:\test folder\file.wav', '-y']

    :param command_string: string of command line as you would execute on cmd.
    :return: list, of divided arguments.
    """

    return shlex.split(command_string)


def join_cmd_to_string(command_list: list) -> str:
    """
    Function gets command list of divided arguments and returns command line string.
    Example:
        ['ffmpeg.exe', '-i', 'c:\test folder\file.mp3', 'c:\test folder\file.wav', '-y']
    Returns:
        ffmpeg.exe -i "c:\test folder\file.mp3" "c:\test folder\file.wav" -y

    :param command_list: list of divided arguments.
    :return: string of command line.
    """

    return shlex.join(command_list)

# v1.0.0 - 02.04.2023 16:20
import traceback


def get_as_string(one_line: bool = False, replace_end: str = str()) -> str:
    """
    Returns traceback as string.

    :param one_line: If 'True', traceback will be returned as one line.
    :param replace_end: If 'one_line' is 'True', this string will be used to replace '\n' in traceback.
    :return: Traceback as string.
    """

    if not one_line:
        return traceback.format_exc()
    else:
        return traceback.format_exc().replace('\n', replace_end)

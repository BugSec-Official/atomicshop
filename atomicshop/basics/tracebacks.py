import traceback


def get_as_string(
        exc: BaseException = None,
        one_line: bool = False,
        replace_end: str = str()
) -> str:
    """
    Returns traceback as string.

    :param exc: Exception to get traceback from. If 'None', current exception will be used.
    :param one_line: If 'True', traceback will be returned as one line.
    :param replace_end: If 'one_line' is 'True', this string will be used to replace '\n' in traceback.
    :return: Traceback as string.
    """

    if exc is None:
        stringed_exception: str = traceback.format_exc()
    else:
        stringed_exception: str = ''.join(traceback.TracebackException.from_exception(exc).format())

    if not one_line:
        return stringed_exception
    else:
        return stringed_exception.replace('\n', replace_end)

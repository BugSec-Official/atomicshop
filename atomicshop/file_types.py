from typing import Union

import magic


def get_mime_type(file_object: Union[str, bytes]):
    """
    Determine the MIME type of the given input.
    The input can be a file path (string) or a bytes object.

    :param file_object: File path as a string or bytes object.
    :return: MIME type as a string.
    """
    mime = magic.Magic(mime=True)

    # Check if input is a file path (str) or bytes
    if isinstance(file_object, str):
        # Assuming input_data is a file path
        return mime.from_file(file_object)
    elif isinstance(file_object, bytes):
        # Assuming input_data is bytes
        return mime.from_buffer(file_object)
    else:
        raise TypeError("Input must be a file path (str) or bytes object.")

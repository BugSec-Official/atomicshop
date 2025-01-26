from typing import Union
import string


def get_single_byte_from_byte_string(byte_string, index: int):
    """
    Function extracts single byte as byte from byte string object.
    The problem: When you slice only the index from bytes string:
        byte_string = b'12345'
        byte_string[0]
    Integer is returned:
        49
    If you want to return byte object, you need to provide range:
        byte_string[0:1]
    This will return:
        b'1'

    :param byte_string: bytes, byte string from which will be sliced the 'index'.
    :param index: integer, place to cut the single byte.
    :return: byte
    """

    return byte_string[index:index+1]


def convert_sequence_of_bytes_to_sequence_of_strings(byte_sequence: bytes) -> list[str]:
    """
    Convert sequence of bytes to sequence of strings.
    :param byte_sequence: bytes, sequence of bytes.
    :return: list of strings.
    """

    result: list[str] = list()
    for byte_index, single_byte in enumerate(byte_sequence):
        # Convert byte to string character.
        string_from_byte = chr(single_byte)

        # Check if string is alphanumeric.
        if string_from_byte.isalnum():
            # Append string to result.
            result.append(string_from_byte)
        # If string is not alphanumeric, it means that it is something like '\x04'.
        # So, we need to output '04'. We need to remove the '\x' from the string.
        # The problem is that the string doesn't contain 4 characters, but 1.
        # len(string_from_byte) returns 1.
        # So, we can't remove '\x' from the string, since it is the character '\x04' in the table.
        # We will convert it to printable string with repr() function.
        # repr() function returns string with quotes, so we need to remove them with [1:-1].
        else:
            printable_string = repr(string_from_byte)[1:-1]
            # Remove '\x' from the string.
            printable_string = printable_string.replace('\\x', '')
            result.append(printable_string)

        # single_byte_string = byte_sequence[byte_index:byte_index+1]

    return result


def convert_sequence_of_bytes_to_exact_string(
        byte_sequence: bytes,
        add_space_between_bytes: bool = False,
) -> str:
    """
    Convert sequence of bytes to exact string.
    Example: b'\xc0\x00' -> 'c000'

    :param byte_sequence: bytes, sequence of bytes.
    :param add_space_between_bytes: bool, add space between bytes.
        Example: b'\xc0\x00' -> 'c0 00'
    :return: string.
    """

    # Convert to hex string and format
    byte_list: list = []
    for byte in byte_sequence:
        byte_list.append(f'{byte:02x}')

    result = ''.join(byte_list)

    return result


def find_position(target: bytes, file_path: str = None, file_bytes: bytes = None, chunk_size: int = None, starting_position: int = 0) -> int:
    """
    Find position of the target bytes string in the file.

    :param target: bytes, target bytes string.
    :param file_path: string, path to file.
    :param file_bytes: bytes, bytes string of the file.
    :param chunk_size: integer, chunk size  in bytes.
    :param starting_position: integer, starting position in bytes. You can specify the starting seeking point
        in the file.
    :return:
    """

    def read_chunk(position):
        if file_path:
            return file.read(chunk_size)
        else:
            end_position = min(position + chunk_size, len(file_bytes))
            return file_bytes[position:end_position]

    if not chunk_size:
        chunk_size = len(target)

    # chunk_size = 4096  # You can adjust the chunk size based on your needs

    # Overlap between chunks to ensure target isn't split between chunks
    overlap_size = len(target) - 1

    # Update the position variable to match the starting position.
    position = starting_position

    # Check if file_bytes is provided, otherwise read from the file path
    if file_bytes is not None:
        file = file_bytes
        length = len(file_bytes)
    else:
        if not file_path:
            raise ValueError("Either file_path or file_bytes must be provided.")
        file = open(file_path, 'rb')
        # Move the file cursor to the starting position.
        file.seek(starting_position)

    # try-finally block to ensure the file is closed properly if opened.
    try:
        chunk = read_chunk(position)

        while chunk:
            index = chunk.find(target)
            if index != -1:
                # Return the absolute position of the target in the file
                return position + index

            # Move the file cursor back by the overlap size to ensure target isn't split between chunks.
            # Get the current position of the cursor in the file.

            # Update position differently depending on the input type
            if file_path:
                position = file.tell() - overlap_size
                file.seek(position)
            else:
                position += chunk_size - overlap_size

            chunk = read_chunk(position)

    finally:
        if file_path:
            file.close()

    # Return -1 if the target is not found
    return -1


def read_bytes_from_position(
        starting_position: int,
        num_bytes: int,
        file_path: str = None,
        file_bytes: bytes = None
) -> bytes:
    """
    Read bytes from specified position in the file.
    :param starting_position: integer, starting position in bytes.
    :param num_bytes: integer, number of bytes to read.
    :param file_path: string, path to file.
    :param file_bytes: bytes, bytes string of the file.
    :return: bytes.
    """

    if not file_path and not file_bytes:
        raise ValueError("Either file_path or file_bytes must be provided.")

    if file_bytes is not None:
        # Ensure starting position and number of bytes are within the length of file_bytes
        if starting_position < 0 or starting_position + num_bytes > len(file_bytes):
            raise ValueError("Starting position and number of bytes to read are out of bounds.")
        return file_bytes[starting_position:starting_position + num_bytes]

    with open(file_path, 'rb') as file:
        # Move the file cursor to the specified position.
        file.seek(starting_position)
        # Read the specified number of bytes.
        data = file.read(num_bytes)
    return data


def convert_bytes_to_printable_string_only(
        byte_sequence: Union[bytes, bytearray],
        non_printable_character: str = '.'
) -> str:
    """
    Convert bytes to printable string. If byte is not printable, replace it with 'non_printable_character'.
    :param byte_sequence: bytes or bytearray, sequence of bytes.
    :param non_printable_character: string, character to replace non-printable characters.
    :return:
    """

    printable = set(string.printable)
    return ''.join(chr(byte) if chr(byte) in printable else non_printable_character for byte in byte_sequence)
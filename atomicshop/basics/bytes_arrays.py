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


def find_position(file_path: str, target: bytes, chunk_size: int = None, starting_position: int = 0) -> int:
    """
    Find position of the target bytes string in the file.

    :param file_path: string, path to file.
    :param target: bytes, target bytes string.
    :param chunk_size: integer, chunk size  in bytes.
    :param starting_position: integer, starting position in bytes. You can specify the starting seeking point
        in the file.
    :return:
    """

    if not chunk_size:
        chunk_size = len(target)

    # chunk_size = 4096  # You can adjust the chunk size based on your needs

    # Overlap between chunks to ensure target isn't split between chunks
    overlap_size = len(target) - 1

    with open(file_path, 'rb') as file:
        # Move the file cursor to the starting position.
        file.seek(starting_position)
        # Update the position variable to match the starting position.
        position = starting_position
        chunk = file.read(chunk_size)

        while chunk:
            index = chunk.find(target)
            if index != -1:
                # Return the absolute position of the target in the file
                return position + index

            # Move the file cursor back by the overlap size to ensure target isn't split between chunks
            file.seek(position + chunk_size - overlap_size)
            # Get the current position of the cursor in the file.
            position = file.tell()
            chunk = file.read(chunk_size)

    # Return -1 if the target is not found
    return -1


def read_bytes_from_position(file_path: str, starting_position: int, num_bytes: int) -> bytes:
    """
    Read bytes from specified position in the file.
    :param file_path: string, path to file.
    :param starting_position: integer, starting position in bytes.
    :param num_bytes: integer, number of bytes to read.
    :return: bytes.
    """

    with open(file_path, 'rb') as file:
        # Move the file cursor to the specified position.
        file.seek(starting_position)
        # Read the specified number of bytes.
        data = file.read(num_bytes)
    return data

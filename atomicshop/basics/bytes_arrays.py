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

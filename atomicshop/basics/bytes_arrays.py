# v1.0.0
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

# v1.0.1 - 21.02.2023 15:30
def convert_hex_string_to_bytes(hex_string: str):
    """
    Example of hex:
        AF 63 CD
    In this case:
        hex_string = 'AF63CD'
    Usage:
        convert_hex_string_to_bytes('AF63CD')
    Returns:
        b'\xafc\xcd'

    :param hex_string: string, that contains hex.
    :return: byte string.
    """

    # The same can be done also with:
    # import binascii
    # bytes_object: bytes = binascii.unhexlify(hex_string)
    return bytes.fromhex(hex_string)


def convert_byte_string_to_string_of_hex(byte_string) -> str:
    """
    Example:
        b'\xde\xad\xbe\xef'.hex()
    Returns:
        'deadbeef'

    :param byte_string: bytes or mutable bytearray object.
    :return: string of hex representation.
    """

    return byte_string.hex()


def convert_integer_to_string_of_hex(integer_object: int) -> str:
    """
    Example:
        hex(126)
    Returns:
        '0x7e'

    :param integer_object: integer.
    :return: string of hex.
    """

    return hex(integer_object)

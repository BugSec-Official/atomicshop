# v1.0.1 - 26.03.2023 - 23:30
import uuid


def generate_random_guid() -> str:
    """
    'uuid.uuid4()' generates the 'uuid.UUID' object and str converts it to string.
    Example result of 'uuid.uuid4()':
        UUID('11111111-1111-1111-1111-111111111111')
    Adding string:
        '11111111-1111-1111-1111-111111111111'

    :return: string.
    """

    return str(uuid.uuid4())

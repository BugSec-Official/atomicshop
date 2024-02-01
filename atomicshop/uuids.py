import uuid


"""
Choosing Between UUID Versions
UUID1: Use it if you need to trace back the machine that generated the UUID.
UUID4: Use it for almost everything else, where you need a unique ID without any other implications.
UUID3 and UUID5: Use them if you need consistent UUIDs generated from the same namespace and name.

Most of the time, uuid4() is preferred due to its simplicity and randomness, 
ensuring a very low probability of ID collision without depending on the machine's identity or the exact timestamp.

Collisions:
The number of random version-4 UUIDs which need to be generated in order to have a 50% probability of at least 
one collision is 2.71 quintillion. This number is equivalent to generating 1 billion UUIDs per second for about
85 years. The probability of one collision would be approximately 50% if every person on earth owns 600 million UUIDs.
https://en.wikipedia.org/wiki/Universally_unique_identifier#Random_UUID_probability_of_duplicates
"""


def generate_uuid4_random(convert_to_hex: bool = True) -> str:
    """
    Generate a random UUID4.

    The hex attribute of a UUID object in Python returns the hexadecimal representation of the UUID as a
    string of 32 hexadecimal digits. This is a more compact form compared to the standard string representation
    returned by str(uuid.uuid4()), which includes hyphens.

    Here's a comparison:
    With Hyphens (Default String Representation): The default string representation of a UUID includes hyphens,
    separating it into five groups, such as 12345678-1234-5678-1234-567812345678.
    This format is easy to read and is often used in textual representations where readability is a concern.

    Hexadecimal (Compact Representation): The hex attribute removes the hyphens and returns the UUID as a continuous
    string of 32 hexadecimal characters, like 12345678123456781234567812345678.
    This compact form might be preferred when you need a shorter version of the UUID for systems that
    don't accept hyphens or when saving space is a priority.

    :return:
    """

    if convert_to_hex:
        return uuid.uuid4().hex
    else:
        return str(uuid.uuid4())

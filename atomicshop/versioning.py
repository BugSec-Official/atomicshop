from typing import Union


def is_target_newer(
        base_version: Union[str, tuple],
        target_version: Union[str, tuple]
):
    """
    Check if the target version is newer than the base version.
    Example: is_target_newer('1.0.0', '1.0.1') -> True
    Example: is_target_newer('1.0.0', '1.0.0') -> False
    Example: is_target_newer('1.0.1', '1.0.0') -> False
    Example: is_target_newer('1.0.1', '1.0.2') -> True
    Example: is_target_newer((1,0,1), (1,1,0)) -> True

    :param base_version: The base version to compare against.
    :param target_version: The target version to compare.
    """

    # Convert string to tuple if string was passed.
    if isinstance(base_version, str):
        base_version = tuple(map(int, base_version.split('.')))
    if isinstance(target_version, str):
        target_version = tuple(map(int, target_version.split('.')))

    # Compare the versions.
    return target_version > base_version
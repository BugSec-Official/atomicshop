def check_3_booleans_when_only_1_can_be_true(boolean1: tuple, boolean2: tuple, boolean3: tuple) -> None:
    """
    Example:
        check_3_booleans_when_only_1_can_be_true(
            (self.config['section']['default_usage'], 'default_usage'),
            (self.config['section']['create_usage'], 'create_usage'),
            (self.config['section']['custom_usage'], 'custom_usage'))
    :param boolean1: tuple, first entry contains the value, second contains the name of the setting.
    :param boolean2: tuple, first entry contains the value, second contains the name of the setting.
    :param boolean3: tuple, first entry contains the value, second contains the name of the setting.
    :return:
    """

    check_if_3_booleans_are_false(boolean1, boolean2, boolean3)
    check_if_2_booleans_are_true(boolean1, boolean2)
    check_if_2_booleans_are_true(boolean1, boolean3)
    check_if_2_booleans_are_true(boolean2, boolean3)


def check_if_3_booleans_are_false(boolean1: tuple, boolean2: tuple, boolean3: tuple):
    if not boolean1[0] and not boolean2[0] and not boolean3[0]:
        message = f"All the boolean settings in config ini file were set to 'False',\n" \
                  f"You need at least one 'True':\n" \
                  f"{boolean1[1]}={boolean1[0]}\n" \
                  f"{boolean2[1]}={boolean2[0]}\n" \
                  f"{boolean3[1]}={boolean3[0]}"
        raise ValueError(message)


def check_if_2_booleans_are_true(boolean1: tuple, boolean2: tuple) -> None:
    if boolean1[0] and boolean2[0]:
        message = f"Only one configuration can be 'True':\n" \
                  f"{boolean1[1]}={boolean1[0]}\n" \
                  f"{boolean2[1]}={boolean2[0]}\n"
        raise ValueError(message)

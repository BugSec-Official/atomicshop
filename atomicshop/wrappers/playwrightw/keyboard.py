def type_text(page, text):
    # Directly type into the focused field (if the cursor is already there)
    page.keyboard.type(text)


def press_key(page, key: str):
    """
    Press a key on the keyboard.
    :param page: playwright page
    :param key: str, the key to press. Example: 'Enter'.
    :return:
    """
    # Optionally, you can press Enter or other keys as needed
    page.keyboard.press(key)

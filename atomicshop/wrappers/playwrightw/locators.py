def get_by_tag(page_or_locator, tag_name: str, attribute: str, value: str):
    """
    Function gets playwright locator by object name, property name and value string.
    Example:
        tag_name='div', property='class', value='test'
    tests for html:
        <div class="test">
    Returns locator:
        page_locator.locator('div[class="test"]')

    :param page_or_locator: 'playwright.page' object or another locator, which is the same for playwright.
    :param tag_name: string of html tag name.
    :param attribute: string of attribute name of the specified html tag name.
    :param value: string value of the specified attribute.
    :return: playwright locator.
    """

    return page_or_locator.locator(f'{tag_name}[{attribute}="{value}"]')


def get_by_text(page_or_locator, text: str):
    return page_or_locator.locator(f"text={text}")


def get_by_tagname_and_text(page_or_locator, tag_name: str, text: str):
    """
    Function gets playwright locator by html tag name and text string.
    Example:
        tag_name='a', text='test'
    tests for html:
        <a>test</a>

    Currently tested:
    'a' - returns playwright locator with 'link' role.
    'button' - returns playwright locator with 'button' role.

    :param page_or_locator:
    :param tag_name: HTML tag name.
    :param text: visual text on the html tag.
    :return: locator.
    """
    if tag_name == "a":
        tag_name = "link"
    elif tag_name == "button":
        pass
    else:
        pass

    return page_or_locator.get_by_role(tag_name, name=text)


def get_framelocator_by_tag(page_or_locator, tag_name: str, attribute: str, value: str):
    """
    Function gets playwright locator by html tag name, property name and value string.
    Example:
        tag_name='div', property='class', value='test'
    tests for html:
        <div class="test">
    Returns locator:
        page_or_locator.locator('div[class="test"]')

    :param page_or_locator: 'playwright.page' object or another locator, which is the same for playwright.
    :param tag_name: string of html tag name.
    :param attribute: string of attribute name of the specified tag_name.
    :param value: string value of the specified attribute.
    :return: playwright locator.
    """

    return page_or_locator.frame_locator(f'{tag_name}[{attribute}="{value}"]')

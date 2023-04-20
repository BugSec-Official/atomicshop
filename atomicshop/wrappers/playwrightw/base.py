def navigate_to_url(page, url: str):
    page.goto(url)


def page_refresh(page):
    """
    Refresh the page like [F5].
    """

    # 'delay=1000' simulates 1 second of user button press.
    # page.keyboard.press('F5', delay=1000)
    page.reload()


def get_url(page):
    """
    Get the current URL of the page.

    :param page:
    :return:
    """

    return page.url


def get_first_locator(locator):
    return locator.first()


def get_first_locator_by_nth(locator):
    return locator.nth(0)


def get_attribute_value_of_locator(page_locator, attribute: str):
    return page_locator.get_attribute(attribute)


def fill_text_in_locator(locator, fill_text: str):
    locator.fill(fill_text)


def click_locator(locator, timeout: int = 30000) -> None:
    """
    Checking the 'Auto-wait' explanation from official docs:
    https://playwright.dev/docs/actionability
    'locator.click()' gets 'True' on following methods:
    Attached, Visible, Stable, Receives Events, Enabled.
    Since locator has only these methods:
    locator.isChecked(), locator.isDisabled(), locator.isEditable(), locator.isEnabled(), locator.isHidden(),
    locator.isVisible().

    :param locator:
    :param timeout:
    :return:
    """
    locator.click(timeout=timeout)


def click_force_locator(locator) -> None:
    """
    This function doesn't do any checks whatsoever. The locator can be hidden and invisible.
    This function will click it anyway.
    Documented: https://playwright.dev/python/docs/input#forcing-the-click

    :param locator:
    :return:
    """
    locator.dispatch_event('click')


def get_locator_text(locator):
    return locator.text_content()


def locator_is_visible(locator) -> bool:
    if locator.is_visible():
        return True
    else:
        return False


def check_locator_is_enabled(locator) -> bool:
    if locator.is_enabled():
        return True
    else:
        return False


def is_more_than_0_elements(locator) -> bool:
    if locator.count() > 0:
        return True
    else:
        return False


def get_position_and_size_of_locator(locator):
    """
    The function returns dict with 4 keys:
        'x': X position of top left corner of an element.
        'y': Y position of top left corner of an element.
        'width': Width of an element.
        'height': Height of an element.

    Calculating the X and Y position of the element example:
        box = get_position_and_size_of_locator(locator)
        # Divide width by 2 and add it to the top left X position.
        box_x_center: int = box["x"] + box["width"] / 2
        # Divide height by 2 and add it to the top left Y position.
        box_y_center: int = box["y"] + box["height"] / 2

    Returns None if the element is not visible.

    :param locator:
    :return:
    """
    return locator.bounding_box()

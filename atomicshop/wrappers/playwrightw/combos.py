from . import locators, base, waits, mouse


def navigate_to_url___wait_maximum_idle(page, url: str, **kwargs) -> None:
    base.navigate_to_url(page, url)
    waits.maximum_idle(page, **kwargs)


def page_refresh___wait_maximum_idle(page, **kwargs) -> None:
    base.page_refresh(page)
    waits.maximum_idle(page, **kwargs)


def locator_is_enabled___is_visible(locator) -> bool:
    """
    Function checks that the 'locator.is_enabled()' and 'locator.is_visible()'.

    :param locator:
    :return:
    """

    if base.check_locator_is_enabled(locator) and base.locator_is_visible(locator):
        return True
    else:
        return False


def get_locator_by_text___is_visible(page_or_locator, text: str) -> bool:
    locator = locators.get_by_text(page_or_locator, text)
    return base.locator_is_visible(locator)


def get_locator_by_text___is_enabled___is_visible(page_or_locator, text: str) -> bool:
    current_locator = locators.get_by_text(page_or_locator, text)
    return locator_is_enabled___is_visible(current_locator)


def get_locator_by_text___click(page_or_locator, text: str) -> None:
    current_locator = locators.get_by_text(page_or_locator, text)
    base.click_locator(current_locator)


def get_locator_by_tag___is_visible(
        page_or_locator, tag_name: str, attribute: str, value: str) -> bool:
    current_locator = locators.get_by_tag(page_or_locator, tag_name, attribute, value)
    return base.locator_is_visible(current_locator)


def get_locator_by_tag___fill_text(
        page_or_locator, tag_name: str, attribute: str, value: str, fill_text) -> None:
    current_locator = locators.get_by_tag(page_or_locator, tag_name, attribute, value)
    base.fill_text_in_locator(current_locator, fill_text)


def get_locator_by_tag___click(
        page_or_locator, tag_name: str, attribute: str, value: str, timeout: int = 30000) -> None:
    current_locator = locators.get_by_tag(page_or_locator, tag_name, attribute, value)
    base.click_locator(current_locator, timeout=timeout)


def get_locator_by_tag___get_text(page_or_locator, tag_name: str, attribute: str, value: str) -> str:
    current_locator = locators.get_by_tag(page_or_locator, tag_name, attribute, value)
    return base.get_locator_text(current_locator)


def get_locator_by_tag___wait_for_locator_to_be_hidden(
        page_or_locator, tag_name: str, attribute: str, value: str, timeout: int = 30000):
    current_locator = locators.get_by_tag(page_or_locator, tag_name, attribute, value)
    waits.wait_for_locator_to_be_hidden(current_locator, timeout=timeout)


def get_locator_by_tag___wait_not_to_be_hidden(
        page_or_locator, tag_name: str, attribute: str, value: str, timeout: int = 30000) -> str:
    current_locator = locators.get_by_tag(page_or_locator, tag_name, attribute, value)
    return waits.wait_for_locator_not_to_be_hidden(current_locator, timeout)


def get_locator_by_tag___wait_not_to_be_hidden___get_text(
        page_or_locator, tag_name: str, attribute: str, value: str, timeout: int = 30000) -> str:
    current_locator = locators.get_by_tag(page_or_locator, tag_name, attribute, value)
    waits.wait_for_locator_not_to_be_hidden(current_locator, timeout)
    return base.get_locator_text(current_locator)


def get_locator_by_tag___get_position_and_size(
        page_or_locator, tag_name: str, attribute: str, value: str):
    current_locator = locators.get_by_tag(page_or_locator, tag_name, attribute, value)
    return base.get_position_and_size_of_locator(current_locator)


def get_locator_by_tag___find_position___click_mouse(
        page, locator, tag_name: str, attribute: str, value: str):
    # Get position and size of locator.
    element_position_size = get_locator_by_tag___get_position_and_size(
        locator, tag_name, attribute, value)
    # Get X and Y position of center of the element.
    x_pos: int = element_position_size["x"] + element_position_size["width"] / 2
    y_pos: int = element_position_size["y"] + element_position_size["height"] / 2

    mouse.click(page, x_pos, y_pos)


def get_locator_by_tag___find_position___move___click_mouse(
        page, locator, tag_name: str, attribute: str, value: str):
    # Get position and size of locator.
    element_position_size = get_locator_by_tag___get_position_and_size(
        locator, tag_name, attribute, value)
    # Get X and Y position of center of the element.
    x_pos: int = element_position_size["x"] + element_position_size["width"] / 2
    y_pos: int = element_position_size["y"] + element_position_size["height"] / 2

    mouse.move(page, x_pos, y_pos, steps=100)
    mouse.click(page, x_pos, y_pos)


def get_locator_by_tagname_and_text___click(
        page_or_locator, tag_name: str, text: str):
    current_locator = locators.get_by_tagname_and_text(page_or_locator, tag_name, text)
    base.click_locator(current_locator)


def get_locator_by_tagname_and_text___click___wait_maximum_idle(
        page, locator, tag_name: str, text: str, **kwargs):
    """
    Function clicks on the locator by tag name and text and waits maximum idle.

    :param page: page is needed to wait for maximum idle.
    :param locator: locator can be also page.
        Example:
            page = browser.new_page()
            page.goto('https://test.com/')
            get_locator_by_tagname_and_text___click___wait_maximum_idle(page, page, 'button', 'English')
    :param tag_name: HTML tag name.
    :param text: visual text on the html tag.
    :return:
    """
    current_locator = locators.get_by_tagname_and_text(locator, tag_name, text)
    base.click_locator(current_locator)
    waits.maximum_idle(page, **kwargs)


def find_position_of_locator___click_mouse(page, locator):
    # Get position and size of locator.
    element_position_size = base.get_position_and_size_of_locator(locator)
    # Get X and Y position of center of the element.
    x_pos: int = element_position_size["x"] + element_position_size["width"] / 2
    y_pos: int = element_position_size["y"] + element_position_size["height"] / 2

    mouse.click(page, x_pos, y_pos)

from . import combos, javascript
from ...file_io import file_io


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


def set_page_print_emulation(page) -> None:
    """
    Emulates 'print' media type screen.

    :param page:
    :return:
    """

    page.emulate_media(media="print")


def get_page_screenshot(
        page, img_type: str = 'png', path: str = None, full_page: bool = False, print_emulation: bool = False) -> bytes:
    """
    Take a screenshot of the page.
    The difference between taking screenshot of a page and locator, that locator doesn't have 'full_page' argument.
    If you don't provide the 'path' argument, the screenshot will be returned as a bytes object anyway.

    :param page:
    :param img_type: Specify screenshot type, can be either "png" or "jpeg". Defaults to 'png'.
    :param path: The file path to save the image to.
    :param full_page: When true, takes a screenshot of the full scrollable page. Defaults to 'False'.
        This parameter doesn't always work if 'True', it saves screenshot only of the view port.
        So you can try using different methods, like print to PDF.
    :param print_emulation: Emulates 'print' media type screen. Defaults to 'False'.

    :return: returns the bytes of the buffer with the captured screenshot.
    """

    if print_emulation:
        set_page_print_emulation(page)

    result_bytes = page.screenshot(full_page=full_page, type=img_type)

    # Save the file.
    # "page.screenshot" has an attribute "path", which saves the bytes to file, but it doesn't work in thread.
    # page.screenshot(full_page=full_page, type=img_type, path=path)
    # So we do it manually.
    if path:
        file_io.write_file(content=result_bytes, file_path=path, file_mode='wb')

    return result_bytes


def _get_full_page_screenshot_with_pillow(
        page, path: str = None, scrolling_method: str = 'mouse', manual_scrolling: int = 0) -> any:
    """
    This function is for reference purposes only and can be useful in the future for alternative methods for
    taking full page screenshots, since 'full_page' attribute of 'screenshot' might not always work.

    Take a screenshot of the full page.
    Aggregate screenshots of the page by scrolling the page and taking screenshots of each viewport, then concatenate
    them vertically using Pillow library.

    :param page:
    :param path: The file path to save the image to.

    :return: returns the buffer with the captured screenshot in Pillow format.
    """

    # Get the total height of the page
    total_height = javascript.get_page_total_height(page)
    current_height = javascript.get_page_viewport_height(page)

    # Set the viewport height
    viewport_height = 900
    page.set_viewport_size({"width": 1440, "height": viewport_height})

    # Capture the screenshots
    images = []
    if manual_scrolling == 0:
        for offset in range(0, total_height, viewport_height):
            combos.scroll_down(page, offset=offset, scrolling_method=scrolling_method)

            images.append(get_page_screenshot(page))
    else:
        for scroll in range(0, manual_scrolling):
            combos.scroll_down(page, offset=viewport_height, scrolling_method=scrolling_method)

            images.append(get_page_screenshot(page))

    # Concatenate images vertically
    from PIL import Image
    import io

    # final_image = Image.new("RGB", (1440, total_height))
    final_image = Image.new("RGB", (1440, viewport_height * len(images)))
    y_offset = 0
    for image_data in images:
        image = Image.open(io.BytesIO(image_data))
        final_image.paste(image, (0, y_offset))
        y_offset += viewport_height

    # Save the final image
    final_image.save(path)

    return final_image


def get_locator_screenshot(locator, img_type: str = 'png', path: str = None) -> bytes:
    """
    Take a screenshot of the locator.
    The difference between taking screenshot of a page and locator, that locator doesn't have 'full_page' argument.
    If you don't provide the 'path' argument, the screenshot will be returned as a bytes object anyway.

    :param locator:
    :param img_type: Specify screenshot type, can be either "png" or "jpeg". Defaults to 'png'.
    :param path: The file path to save the image to.

    :return: returns the bytes of the buffer with the captured screenshot.
    """

    return locator.screenshot(type=img_type, path=path)


def get_page_pdf(page, path: str = None, print_background: bool = True, print_format: str = 'A4') -> bytes:
    """
    Print page as PDF.
    If you don't provide the 'path' argument, the PDF will be returned as a bytes object anyway.

    :param page:
    :param path: The file path to save the PDF to.
    :param print_background: Print background graphics. Defaults to 'True'.
    :param print_format: Paper format. If set, takes priority over width or height options. Defaults to 'A4'.
    """

    result_bytes = page.pdf(print_background=print_background, format=print_format)

    # Save the PDF to file.
    # "page.pdf" has an attribute "path", which saves the bytes to file, but it doesn't work in thread.
    # page.pdf(path=path, print_background=print_background, format=print_format)
    # So we do it manually.
    if path:
        file_io.write_file(content=result_bytes, file_path=path, file_mode='wb')

    return result_bytes


def get_page_html(page, path: str = None, convert_to_bytes: bool = False, print_kwargs: dict = None) -> any:
    """
    Get the full HTML contents of the page, including the doctype.

    :param page:
    :param path: The file path to save the HTML to.
    :param convert_to_bytes: If 'True', converts the HTML string to bytes object.
    :param print_kwargs: dict, that contains all the arguments for 'print_api' function.

    :return: returns the HTML content.
    """

    result = page.content()
    if path:
        file_io.write_file(content=result, file_path=path, **print_kwargs)

    if convert_to_bytes:
        result = result.encode('utf-8')

    return result


def get_page_txt(page, path: str = None, convert_to_bytes: bool = False, print_kwargs: dict = None) -> any:
    """
    Get the full text contents of the page.

    :param page:
    :param path: The file path to save the txt to.
    :param convert_to_bytes: If 'True', converts the text string to bytes object.
    :param print_kwargs: dict, that contains all the arguments for 'print_api' function.

    :return: returns the text content.
    """

    result = javascript.get_page_text_content(page)

    if path:
        file_io.write_file(content=result, file_path=path, **print_kwargs)

    if convert_to_bytes:
        result = result.encode('utf-8')

    return result


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

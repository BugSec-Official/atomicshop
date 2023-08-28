"""
Mouse file contains mouse actions in Playwright.
"""


def move(page, x_pos: int, y_pos: int, steps: int):
    # This move is done by playwright, doesn't evade bot recognition.
    page.mouse.move(x=x_pos, y=y_pos, steps=steps)


def click(page, x_pos: int, y_pos: int):
    # This click is done by playwright, doesn't evade bot recognition. Almost the same as 'locator.click()'.
    page.mouse.click(x=x_pos, y=y_pos)


def scroll_down(page, offset: int) -> None:
    """
    Scroll down the page.

    :param page: Playwright page.
    :param offset: integer, of pixels to scroll down
    """

    page.mouse.wheel(0, offset)

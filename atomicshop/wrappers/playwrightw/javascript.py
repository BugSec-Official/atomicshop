"""
Javascript file contains javascript evaluations in Playwright.
"""


def scroll_down(page, offset: int) -> None:
    """
    Scroll down the page.

    :param page: Playwright page.
    :param offset: integer, of pixels to scroll down
    """

    page.evaluate(f"window.scrollTo(0, {offset})")


def get_page_total_height(page) -> int:
    """
    Get total height of the page.

    :param page: Playwright page.
    :return: integer, total height of the page.
    """

    return page.evaluate("document.body.scrollHeight")


def get_page_viewport_height(page) -> int:
    """
    Get viewport height of the page.

    :param page: Playwright page.
    :return: integer, viewport height of the page.
    """

    return page.evaluate("window.innerHeight")

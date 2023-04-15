from atomicshop.print_api import print_api

from playwright.sync_api import expect
# This is from official docs: https://playwright.dev/python/docs/api/class-timeouterror
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


"""
Navigation lifecycle
Playwright splits the process of showing a new document in a page into navigation and loading.

Navigation starts by changing the page URL or by interacting with the page (e.g., clicking a link). The navigation 
intent may be canceled, for example, on hitting an unresolved DNS address or transformed into a file download.

Navigation is committed when the response headers have been parsed and session history is updated. Only after the 
navigation succeeds (is committed), the page starts loading the document.

Loading covers getting the remaining response body over the network, parsing, 
executing the scripts and firing load events:

    page.url is set to the new url
    document content is loaded over network and parsed
    page.on("domcontentloaded") event is fired
    page executes some scripts and loads resources like stylesheets and images
    page.on("load") event is fired
    page executes dynamically loaded scripts
    networkidle is fired when no new network requests are made for 500 ms
    
https://playwright.dev/python/docs/navigations
"""


def wait_for_locator_to_be_hidden(locator, timeout=30000):
    """
    Expect 'to_be_hidden' default timeout is 5000ms, changing to playwright default of 30000 for slow sites.
    Meaning this function will wait for the object until locator becomes hidden.

    :param locator:
    :param timeout: integer, of time on milliseconds.
    :return:
    """

    expect(locator).to_be_hidden(timeout=timeout)


def wait_for_locator_not_to_be_hidden(locator, timeout: int = 30000):
    """
    Expect 'not_to_be_hidden' default timeout is 5000ms, changing to playwright default of 30000 for slow sites.
    Meaning this function will wait for the object until locator becomes visible.

    :param locator:
    :param timeout: integer, of time on milliseconds.
    :return:
    """

    expect(locator).not_to_be_hidden(timeout=timeout)


def wait_for_either_of_selectors_visible_on_locator(
        locator, object1: str, attribute1: str, value1: str, object2: str, attribute2: str, value2: str):
    locator.locator(
        f"//{object1}[contains(@{attribute1}, '{value1}')]|//{object2}[contains(@{attribute2}, '{value2}')]"
    ).wait_for()


def networkidle(page, timeout=30000) -> None:
    """
    Wait for network to be idle - stop loading files.
    NetworkIdle event will be triggered after first 500 ms of no network activity.
    The problem is that if there are events that continue to load after 600 ms, the function will not wait for them.
    Also, you can't execute this function twice, since the event was already triggered by playwright the first time.

    :param page:
    :param timeout: integer, of time on milliseconds. 'page.wait_for_load_state' defaults is 30000ms (30 seconds).
    :return: None
    """

    page.wait_for_load_state("networkidle", timeout=timeout)


def domcontentloaded(page, timeout=30000) -> None:
    """
    Wait for domcontentloaded.

    :param page:
    :param timeout: integer, of time on milliseconds. 'page.wait_for_load_state' defaults is 30000ms (30 seconds).
    :return: None
    """

    page.wait_for_load_state("domcontentloaded", timeout=timeout)


def load(page, timeout=30000) -> None:
    """
    Wait for load.

    :param page:
    :param timeout: integer, of time on milliseconds. 'page.wait_for_load_state' defaults is 30000ms (30 seconds).
    :return: None
    """

    page.wait_for_load_state("load", timeout=timeout)


def network_fully_idle(page, timeout: int = 2000, **kwargs) -> None:
    """
    Wait for network to be idle - stop loading files.
    Sometimes, this function alone is not enough, since the loading of the page can stop in the middle
    by Playwright. Not sure why, so just use 'page.wait_for_load_state("load")' as well, before this function
    to make sure the page is fully loaded.

    :param page:
    :param timeout: int, the default timeout for 'page.expect_response' is 30000ms (30 seconds), but since we trigger
        it in loop - each event will have timeout of 30000ms, so we set it to 2000ms (2 seconds), which was optimal
        in the testing.
    :return: None.
    """

    while True:
        try:
            # "**/*" is the wildcard for all URLs.
            # 'page.expect_response' will wait for the response to be received, and then return the response object.
            # When timeout is reached, it will raise a TimeoutError, which will break the while loop.
            with page.expect_response("**/*", timeout=timeout) as response_info:
                print_api(response_info.value, **kwargs)
        except PlaywrightTimeoutError:
            break


def maximum_idle(page, **kwargs) -> None:
    """
    Wait for maximum idle.
    1. 'wait_for_load' - 'page.wait_for_load_state("load")', makes sure that 'some' of the scripts executed and
    resources like styles and images are loaded.
    2. 'wait_for_domcontentloaded' - 'page.wait_for_load_state("domcontentloaded")', by the official docs triggered
    before the 'load' event, but I entered it here anyway to be on the safe side, since in Playwright
    you never know.
    *. 'wait_for_networkidle' - 'page.wait_for_load_state("networkidle")', the last event to be triggered when
    page is loaded. The problem is that it has hardcoded wait of 500ms for idle time and there can be events
    that continue to load after 600ms.
    For some reason 'networkidle' can result in timeout errors, so currently this is disabled.
    3. So, we use 'wait_for_network_fully_idle' to make sure that the rest of events are loaded.
    The problem with this function that it can stop in the middle of the loading of the page, so we use
    'page.wait_for_load_state("load")' as well, before this function to make sure the page is fully loaded.

    :param page:
    :return: None
    """

    print_api('Before wait_for_load', **kwargs)
    load(page)
    print_api('After wait_for_load, Before wait_for_domcontentloaded', **kwargs)
    domcontentloaded(page)
    print_api('After wait_for_domcontentloaded', **kwargs)
    # For some reason 'networkidle' can result in timeout errors, so currently this is disabled.
    # networkidle(page)
    print_api('Before wait_for_network_fully_idle', **kwargs)
    network_fully_idle(page, **kwargs)
    print_api('After wait_for_network_fully_idle', **kwargs)

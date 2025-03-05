"""
Scenarios file contains full execution scenarios of playwright wrapper.
For example: run playwright, navigate to URL, get text from a locator.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Literal

from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup

from . import engine, base, combos
from ...basics import threads, multiprocesses
from ... import web


def get_text_from_html_tag(url: str, tag_name: str, attribute: str, value: str) -> str:
    """
    The function receives playwright engine and page object, navigates to URL,
    gets text from html tag by tag name, property name and value string.

    Example:
        tag_name='div', property='class', value='test'
    tests for html:
        <div class="test">
    Returns text:
        'Some text inside that object'

    :param url: string of URL to navigate to.
    :param tag_name: string of html tag name.
    :param attribute: string of attribute name of the specified html tag name.
    :param value: string value of the specified attribute.
    :return: string text from html tag.
    """

    # Execute playwright engine with default settings
    playwright_engine = engine.PlaywrightEngine(headless=True)
    playwright_engine.start()

    # Navigate to URL.
    combos.navigate_to_url___wait_maximum_idle(playwright_engine.page, url)

    # Get text from html tag.
    result = combos.get_locator_by_tag___get_text(playwright_engine.page, tag_name, attribute, value)

    # Close playwright engine.
    # playwright_engine.stop()

    return result


def get_page_content(
        url: str,
        page_format: str = 'html',
        path: str = None,
        pdf_format: str = 'A4',
        html_txt_convert_to_bytes: bool = True,
        print_kwargs: dict = None
) -> any:
    """
    The function receives playwright engine and page object, navigates to URL, gets page content in specified format,
    saves the file to specified path if provided.

    :param url: string of URL to navigate to.
    :param page_format: string of page format to get. Default is 'html'.
        'html' - returns html string.
        'pdf' - returns pdf binary.
        'png' - returns png binary.
        'jpeg' - returns jpeg binary.
    :param path: string of path to save the file to. Default is None.
    :param pdf_format: string of pdf format, applicable only if 'page_format=pdf'. Default is 'A4'.
    :param html_txt_convert_to_bytes: boolean, applicable only if 'page_format=html' or 'page_format=txt'.
        Default is True.
    :param print_kwargs: dict, that contains all the arguments for 'print_api' function.

    :return: any page content in specified format.
    """

    # Execute playwright engine with default settings
    playwright_engine = engine.PlaywrightEngine(headless=True)
    playwright_engine.start()

    # Navigate to URL.
    combos.navigate_to_url___wait_maximum_idle(playwright_engine.page, url, print_kwargs=print_kwargs)

    # Get page content.
    result = None
    if page_format == 'html':
        result = base.get_page_html(
            playwright_engine.page, path=path, convert_to_bytes=html_txt_convert_to_bytes, print_kwargs=print_kwargs)
    if page_format == 'txt':
        result = base.get_page_txt(
            playwright_engine.page, path=path, convert_to_bytes=html_txt_convert_to_bytes, print_kwargs=print_kwargs)
    elif page_format == 'pdf':
        result = base.get_page_pdf(playwright_engine.page, path=path, print_format=pdf_format)
    elif page_format == 'png':
        result = base.get_page_screenshot(playwright_engine.page, path=path, full_page=True)
    elif page_format == 'jpeg':
        result = base.get_page_screenshot(playwright_engine.page, path=path, full_page=True, img_type='jpeg')

    # playwright_engine.close_browser()
    # Close playwright engine.
    playwright_engine.stop()

    return result


def get_page_content_in_thread(
        url: str,
        page_format: str = 'html',
        path: str = None,
        pdf_format: str = 'A4',
        html_txt_convert_to_bytes: bool = True,
        print_kwargs: dict = None
):
    """
    The function uses 'threads.thread_wrap_var' function in order to wrap the function 'get_page_content' and
    execute it in a thread with arguments and return the result.
    """

    return threads.thread_wrap_var(
            function_reference=get_page_content,
            url=url,
            page_format=page_format,
            path=path,
            pdf_format=pdf_format,
            html_txt_convert_to_bytes=html_txt_convert_to_bytes,
            print_kwargs=print_kwargs
        )


def _get_page_content_in_process(
        url: str, page_format: str = 'html', path: str = None, print_kwargs: dict = None, pdf_format: str = 'A4',
        html_txt_convert_to_bytes: bool = True):
    """
    The function uses 'threads.thread_wrap_var' function in order to wrap the function 'get_page_content' and
    execute it in a thread with arguments and return the result.
    """

    return multiprocesses.process_wrap_queue(
            function_reference=get_page_content,
            url=url,
            page_format=page_format,
            path=path,
            pdf_format=pdf_format,
            html_txt_convert_to_bytes=html_txt_convert_to_bytes,
            print_kwargs=print_kwargs
        )


def fetch_urls_content_in_threads(
        urls: list[str],
        number_of_characters_per_link: int,
        text_fetch_method: Literal[
            'playwright_text',
            'js_text',
            'playwright_html',
            'js_html',
            'playwright_copypaste'
        ]
) -> list[str]:
    """ The function to fetch all URLs concurrently using threads """
    contents = []

    # Use ThreadPoolExecutor to run multiple threads
    with ThreadPoolExecutor() as executor:
        # Submit tasks for each URL
        future_to_url = {executor.submit(_fetch_content, url, number_of_characters_per_link, text_fetch_method): url for url in urls}

        # Collect results as they complete
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                data = future.result()
                contents.append(data)
            except Exception as exc:
                print(f"An error occurred when fetching {url}: {exc}")

    return contents


def fetch_urls_content(
        urls: list[str],
        number_of_characters_per_link: int,
        text_fetch_method: Literal[
            'playwright_text',
            'js_text',
            'playwright_html',
            'js_html',
            'playwright_copypaste'
        ],
) -> list[str]:
    """ The function to fetch all URLs not concurrently without using threads """
    contents = []

    for url in urls:
        data = _fetch_content(url, number_of_characters_per_link, text_fetch_method)
        contents.append(data)

    return contents


def _fetch_content(
        url,
        number_of_characters_per_link,
        text_fetch_method: Literal[
            'playwright_text',
            'js_text',
            'playwright_html',
            'playwright_html_to_text',
            'js_html',
            'js_html_to_text',
            'playwright_copypaste'
        ],
        headless: bool = True):
    """ Function to fetch content from a single URL using the synchronous Playwright API """

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)  # Set headless=True if you don't want to see the browser

        user_agent: str = web.USER_AGENTS['Windows_Chrome_Latest']

        if text_fetch_method == "playwright_copypaste":
            context = browser.new_context(permissions=["clipboard-read", "clipboard-write"], user_agent=user_agent)
        else:
            context = browser.new_context(user_agent=user_agent)

        page = context.new_page()

        # from playwright_stealth import stealth_sync
        # stealth_sync(page)

        # # Block specific script by URL or partial URL match
        # def block_script(route):
        #     if "custom.js" in route.request.url:
        #         print(f"Blocking: {route.request.url}")
        #         route.abort()  # Block the request
        #     else:
        #         route.continue_()  # Allow other requests
        #
        # # Intercept and handle network requests
        # page.route("**/*", block_script)

        page.goto(url)

        # Wait for the page to load using all possible methods, since there is no specific method
        # that will work for all websites.
        page.wait_for_load_state("load", timeout=5000)
        page.wait_for_load_state("domcontentloaded", timeout=5000)
        # The above is not enough, wait for network to stop loading files.
        response_list: list = []
        while True:
            try:
                # "**/*" is the wildcard for all URLs.
                # 'page.expect_response' will wait for the response to be received, and then return the response object.
                # When timeout is reached, it will raise a TimeoutError, which will break the while loop.
                with page.expect_response("**/*", timeout=2000) as response_info:
                    response_list.append(response_info.value)
            except PlaywrightTimeoutError:
                break

        if text_fetch_method == "playwright_text":
            text_content = page.inner_text('body')
        elif text_fetch_method == "js_text":
            # Use JavaScript to extract only the visible text from the page
            text_content: str = page.evaluate("document.body.innerText")
        elif "playwright_html" in text_fetch_method:
            # Get the full HTML content of the page
            text_content = page.content()
        elif "js_html" in text_fetch_method:
            # Use JavaScript to extract the full text from the page
            text_content = page.evaluate('document.documentElement.outerHTML')
        elif text_fetch_method == "playwright_copypaste":
            # Focus the page and simulate Ctrl+A and Ctrl+C
            page.keyboard.press("Control+a")  # Select all text
            page.keyboard.press("Control+c")  # Copy text to clipboard
            # Retrieve copied text from the clipboard
            text_content = page.evaluate("navigator.clipboard.readText()")
        else:
            raise ValueError(f"Invalid text_fetch_method: {text_fetch_method}")

        if "to_text" in text_fetch_method:
            # Convert HTML to plain text using BeautifulSoup
            soup = BeautifulSoup(text_content, "html.parser")
            text_content = soup.get_text()

        # text = page.evaluate('document.body.textContent')
        # text = page.eval_on_selector('body', 'element => element.innerText')
        # text = page.eval_on_selector('body', 'element => element.textContent')
        # text = page.inner_text('body')
        # text = page.text_content('body')

        # text = page.evaluate('document.documentElement.innerText')
        # text = page.inner_text(':root')

        browser.close()
    # Return only the first X characters of the text content to not overload the LLM.
    return text_content[:number_of_characters_per_link]
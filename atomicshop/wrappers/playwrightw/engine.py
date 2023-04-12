import os
import time
import datetime
import random
import getpass
from tempfile import gettempdir

from . import combos

from ...print_api import print_api
from ...keyboard_press import send_alt_tab
from ...filesystem import create_folder

# Web automation library.
from playwright.sync_api import sync_playwright
# Stealth options for playwright. External.
from playwright_stealth import stealth_sync


class PlaywrightEngine:
    """
    PlaywrightEngine class is responsible for Playwright operations.
    """

    def __init__(
            self,
            browser: str = 'chromium', incognito_mode: bool = True, browser_content_working_directory: str = None):
        """
        :param browser: string, specifies which browser will be executed. Playwright default is 'chromium'.
        :param incognito_mode: boolean,
            'True': browser will be used in 'Incognito' mode.
             'False': not be used in incognito mode and 'browser_content' folder will be created to save all
                the session data. Default 'Playwright' behaviour is 'incognito_mode' set to 'True'.
        :param browser_content_working_directory: string, with full path to directory in which will be created
            'browser_content' directory, if 'incognito_mode' mode will be set to 'False'. Meaning, all the cookies
            and user data will be saved to that directory. The default behaviour is empty options,
            to create TEMP folder.

            If the option is not specified, system's %TEMP% folder is used, and 'browser_content' folder
            will be created there.

            Input example:
                D:\\Playwright
            The user files will be saved to:
                D:\\Playwright\\browser_content
        """
        # Variables from input.
        # self.site_instance = site_instance
        self.browser_switch: str = browser
        self.incognito_mode: bool = incognito_mode
        self.browser_content_working_directory: str = browser_content_working_directory

        # Static configuration.
        self.browser_content_directory_name: str = 'browser_content'
        self.browser_content_directory_path: str = str()
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.string_previous: str = str()

    # === Playwright objects definition functions ======================================================================
    def start(self):
        # The documentation states that we need to start Playwright with 'with' statement.
        # Example:
        #  with sync_playwright() as playwright:
        #   self.browser = playwright.chromium.launch(channel=chromium, headless=False)
        # This means that 'sync_playwright()' should have '__enter__()' function defined.
        # Also, 'sync_playwright()' has 'start()' function that executes the '__enter__()' function.
        # So, we can execute only that.
        self.playwright = sync_playwright().start()
        self.execute_browser()

    def stop(self):
        # Finally, 'sync_playwright()' should have '__exit__()' function defined, but '__enter__()' function
        # creates '.stop' attribute for 'playwright' object, which gets the '__exit__' function reference name.
        # playwright.stop = self.__exit__
        # So, we can call 'playwright.stop()' in order to close the object without 'with' statement.
        # noinspection PyStatementEffect,PyUnresolvedReferences
        self.playwright.stop

    def execute_browser(self) -> None:
        """ Execute browser based on mode """

        channel: str = str()
        if self.browser_switch == 'edge':
            channel = 'msedge'
            self.browser_switch = 'chromium'
        elif self.browser_switch == 'chrome':
            channel = 'chrome'
            self.browser_switch = 'chromium'

        selected_browser = None
        if self.browser_switch == 'chromium' or self.browser_switch == 'firefox':
            selected_browser = getattr(self.playwright, self.browser_switch)

        # If incognito mode was selected, this means we execute playwright in regular mode.
        if self.incognito_mode:
            # Executes Chromium browser in regular mode.
            # if set "headless=True" you will not see the browser itself.
            self.browser = selected_browser.launch(channel=channel, headless=False)
            # self.browser = selected_browser.launch(channel="chrome", headless=False)
            # You can run several "page" objects under one context, which runs inside a "browser" object.
            self.context = self.browser.new_context()
            # self.context = self.browser.new_context(
            #     geolocation={"longitude": 0, "latitude": 0},
            #     permissions=["geolocation"]
            # )
            self.page = self.context.new_page()

            # Making playwright stealthier with less footprint of automation.
            stealth_sync(self.page)
        # If Incognito was set to False, then this is setting that will use a folder that is created for all the
        # content like cookies.
        else:
            # If 'browser_content_working_directory' wasn't specified, we'll be using %TEMP% directory.
            if not self.browser_content_working_directory:
                self.browser_content_directory_path = gettempdir() + os.sep + self.browser_content_directory_name
            # If 'browser_content_working_directory' was specified.
            else:
                self.browser_content_directory_path = \
                    self.browser_content_working_directory + os.sep + self.browser_content_directory_name

            # Create folder for 'self.browser_content_directory_path'.
            create_folder(self.browser_content_directory_path)

            self.browser = selected_browser.launch_persistent_context(
                self.browser_content_directory_path, channel=channel, headless=False
            )
            # 'launch_persistent_context' doesn't have a 'new_context()' method, so starting page right away.
            self.page = self.browser.new_page()

    def close_browser(self) -> None:
        self.page.close()
        self.context.close()
        self.browser.close()
        self.stop()

    # === Custom functions =============================================================================================
    def delay_random(self):
        self.page.wait_for_timeout(random.randint(1, 3) * 1000)

    def get_viewport_size(self):
        # The size of the browsing inner window. The resolution you're browsing with. Doesn't have to be the same
        # as your desktop resolution.
        return self.page.viewport_size

    def mouse_move(self, x_pos: int, y_pos: int, steps: int):
        # This move is done by playwright, doesn't evade bot recognition.
        self.page.mouse.move(x=x_pos, y=y_pos, steps=steps)

    def mouse_click(self, x_pos: int, y_pos: int):
        # This click is done by playwright, doesn't evade bot recognition. Almost the same as 'locator.click()'.
        self.page.mouse.click(x=x_pos, y=y_pos)

    def get_locator_by_element___find_position___move___click_mouse(
            self, page_locator, element: str, attribute: str, value: str):
        # Get position and size of locator.
        element_position_size = combos.get_locator_by_tag___get_position_and_size(
            page_locator, element, attribute, value)
        # Get X and Y position of center of the element.
        x_pos: int = element_position_size["x"] + element_position_size["width"] / 2
        y_pos: int = element_position_size["y"] + element_position_size["height"] / 2

        self.mouse_move(x_pos, y_pos, steps=100)
        self.mouse_click(x_pos, y_pos)

    def wait_for_selector_by_object_attribute_value(self, element: str, attribute: str, value: str):
        """
        Waits for object to be visible. If it is hidden, it will wait until timeout and throw exception with
        hidden objects.
        :param element:
        :param attribute:
        :param value:
        :return:
        """
        self.page.wait_for_selector(f'{element}[{attribute}="{value}"]')

    def login(
            self, url_login: str,
            user_box_text: str = str(), pass_box_text: str = str(), submit_button_text: str = str(),
            username: str = str(), password: str = str(),
            credential_single_usage: bool = False
              ) -> None:
        """
        This function navigates to log in URL, but gives the user to interact with the page in order to login.
        After user finish the login process, he may return to the python window and press [Enter] to continue
        automation.

        :param url_login: URL string of the login page.
        :param user_box_text: Text that is shown in the user/email text box.
        :param pass_box_text: Text that is shown in the password text box.
        :param username: string, username that will be used to fill in 'user_box_text'.
        :param password: string, password that will be used to fill in 'pass_box_text'.
        :param submit_button_text: Text that is shown on the submit button.
        :param credential_single_usage: bool, If set to 'True', specified 'username' and 'password' variables will be
            removed from memory. This is not a security solution, since they are still left in deeper memory locators,
            but better than nothing.
        :return: None
        """

        # Navigate to login page.
        self.page.goto(url_login)

        # If username or password text box text wasn't specified, it means we can't find it with playwright to fill the
        # username string or password string.
        if not user_box_text or not pass_box_text:
            # It means that we're using the Site's gui to input username and password each time the script is executed.
            # So, this script will wait for input.
            input("After Login Press Enter to continue...")
        else:
            # if 'username' or 'password' weren't passed, we'll get them from console.
            if not username or not password:
                # Send [Alt]+[Tab] to return to CMD window to input email and password.
                send_alt_tab()

                username = getpass.getpass(prompt="User/Email: ")
                password = getpass.getpass(prompt="Password: ")

            # Input 'username' and 'password' into 'user_box_text' and 'pass_box_text'.
            self.page.get_by_role("textbox", name=user_box_text).fill(username)
            self.page.get_by_role("textbox", name=pass_box_text).fill(password)

            # If 'credential_single_usage' was set to 'True' we'll remove the variables.
            if credential_single_usage:
                del username
                del password

            # Click the submit button.
            self.page.locator("#sign-in-form").get_by_role("button", name=submit_button_text).click()

    def wait_and_reload_page_in_exception(self, exception, time_to_sleep_minutes: int):
        print_api(exception, error_type=True, color="red")
        message = f'Could be the site is down, will retry in {time_to_sleep_minutes} minutes'
        print_api(message, error_type=True, color="red")
        time.sleep(time_to_sleep_minutes * 60)
        # combos.page_refresh___wait_maximum_idle(self.page)

    def check_for_element_change(self, locator_string: str):
        """
        Function gets the locator string input, read text from all the locators that contain this object.
        After that compares the text with previous object text.

        :param locator_string: The locator string object that will be  checked on the page.
        :return: True if the text in the object changed / False if didn't.
        """

        # Get the element from page that contains the needed text.
        element = self.page.locator(locator_string)

        # There could be times that there will be more than one such element on one page or no elements at all.
        element_count = element.count()

        # Get the text out of all elements.
        string_current: str = str()
        for i in range(element_count):
            string_current = string_current + element.nth(i).text_content()

        print_api(f'Current element text of [{locator_string}]: {string_current}', rtl=True)

        # If text from previous cycle isn't the same as text from current cycle, then put the new value to the
        # previous one and return 'True' since the text really changed.
        if self.string_previous != string_current:
            # print(f'Changed: [{string_previous[:10]}] vs [{string_current[:10]}]')
            self.string_previous = string_current
            return True
        # If the text didn't change, just return false.
        else:
            # print(f'Not Changed: [{string_previous[:10]}] vs [{string_current[:10]}]')
            return False

    def count_elements_return_locator(self, locator_string: str):
        """
        Count elements on page and return counter and locator object.

        :param locator_string: String of locator.
        :return: Count integer of all times the locator appears on page, Locator object
        """

        # Define locator for element.
        element = self.page.locator(locator_string)
        # Count the elements on page.
        return element.count(), element

    def get_text_from_all_locators_as_one_string(self, locator_string: str):
        """
        Get the text from all the locators to one string and return it.

        :param locator_string: String of locator.
        :return: String with text from all the locators on page.
        """

        # Get the locator and number of times this locator appears on page.
        count, element = self.count_elements_return_locator(locator_string)

        # Create empty text string.
        text_string: str = str()
        # Loop the number of times in 'count' of the element.
        for i in range(count):
            # Aggregate the text of each element to 'text_string'.
            text_string = text_string + element.nth(i).text_content()

        return text_string

    def get_text_from_all_locators_as_list(self, locator_string: str):
        """
        Get the text from all the locators to one string and return it.

        :param locator_string: String of locator.
        :return: String with text from all the locators on page.
        """

        # Get the locator and number of times this locator appears on page.
        count, element = self.count_elements_return_locator(locator_string)

        # Create empty list.
        list_of_texts: list = list()
        # Loop the number of times in 'count' of the element.
        for i in range(count):
            # Add the text of each element to the list.
            list_of_texts.append(element.nth(i).text_content())

        return list_of_texts

    def end_loop(self, time_to_sleep_minutes: int, **kwargs):
        # Nullifying 'string_previous', so new loop will not have the same one as previous loop in case of error.
        self.string_previous = str()

        print_api('Finished execution Time: ' + str(datetime.datetime.now()), **kwargs)
        print_api('Waiting minutes: ' + str(time_to_sleep_minutes), **kwargs)
        time.sleep(time_to_sleep_minutes * 60)
        print_api('-----------------------------------------', **kwargs)

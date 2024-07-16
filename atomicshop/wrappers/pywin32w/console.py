import win32api
import win32con


class ConsoleHandler:
    """
    This class is used to handle console events.
    Currently used to handle the 'CTRL_CLOSE_EVENT' event - Meaning what to do when the user closes the console by
    clicking on X in the top right corner.
    """
    def __init__(
            self,
            cleanup_action: callable = None,
            args: tuple = None,
            kwargs: dict = None
    ):
        """
        :param cleanup_action: The action to run when user closes the console.
        :param args: The arguments to pass to the cleanup action.
        :param kwargs: The keyword arguments to pass to the cleanup action.
        """
        self.cleanup_action = cleanup_action
        self.args = args
        self.kwargs = kwargs

    def _console_handler(self, event):
        if event == win32con.CTRL_CLOSE_EVENT:
            if self.cleanup_action and callable(self.cleanup_action):
                self.cleanup_action(*self.args, **self.kwargs)
            return True
        return False

    def register_handler(self):
        win32api.SetConsoleCtrlHandler(self._console_handler, True)

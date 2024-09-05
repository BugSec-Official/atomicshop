import ctypes


class NotWindowsConsoleError(Exception):
    pass


# Define QuickEdit mode bit (0x0040)
ENABLE_QUICK_EDIT = 0x0040


def disable_quick_edit():
    """
    Disables QuickEdit mode in the Windows Command Prompt.
    This prevents the console from being paused when the user selects text.
    NO ADMIN REQUIRED
    """

    kernel32 = ctypes.windll.kernel32
    h_stdin = kernel32.GetStdHandle(-10)  # -10 is STD_INPUT_HANDLE

    # Get current console mode
    mode = ctypes.c_uint()
    if kernel32.GetConsoleMode(h_stdin, ctypes.byref(mode)) == 0:
        try:
            raise ctypes.WinError()
        except OSError as e:
            # This means that the code is not running in console window.
            if e.errno == 9 and e.winerror == 6:
                raise NotWindowsConsoleError("This code is not running in a Windows console.")
            else:
                raise e

    # Disable QuickEdit Mode by clearing the corresponding bit
    mode.value &= ~ENABLE_QUICK_EDIT

    # Set the new console mode
    if kernel32.SetConsoleMode(h_stdin, mode) == 0:
        raise ctypes.WinError()

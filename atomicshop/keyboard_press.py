# Basic imports.
import time
import ctypes


def send_alt_tab():
    """
    The function send [Alt]+[Tab] on Windows.

    :return:
    """

    user32 = ctypes.windll.user32
    user32.keybd_event(0x12, 0, 0, 0)  # Alt
    time.sleep(0.2)
    user32.keybd_event(0x09, 0, 0, 0)  # Tab
    time.sleep(0.2)
    user32.keybd_event(0x09, 0, 2, 0)  # Release Tab
    time.sleep(0.2)
    user32.keybd_event(0x12, 0, 2, 0)  # Release Alt

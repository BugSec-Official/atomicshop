import os
import sys


ANSI_END = '\033[0m'


def initialize_ansi() -> None:
    """
    On Windows platforms, this is needed in order for ANSI escape codes to work in CMD.

    :return: None
    """

    if sys.platform.lower() == "win32":
        os.system("")


def get_colors_basic_dict(color):
    colors_basic_dict = {
        'red': ColorsBasic.RED,
        'green': ColorsBasic.GREEN,
        'yellow': ColorsBasic.YELLOW,
        'blue': ColorsBasic.BLUE,
        'header': ColorsBasic.HEADER,
        'cyan': ColorsBasic.CYAN,
        'orange': ColorsBasic.ORANGE
    }

    return colors_basic_dict[color]


# https://en.wikipedia.org/wiki/ANSI_escape_code#Colors
class ColorsBasic:
    """
    Usage 1:
        print(f'{ColorsBasic.GREEN}green{ColorsBasic.END}')
    Usage 2:
        col = ColorsBasic()
        print(f'{col.GREEN}red{col.END}')
    """

    global ANSI_END
    initialize_ansi()

    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    HEADER = '\033[95m'
    CYAN = '\033[96m'
    ORANGE = '\033[38;2;255;165;0m'
    END = ANSI_END


class FontType:
    """
    Same usage as 'ColorsBasic'.
    """

    global ANSI_END
    initialize_ansi()

    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = ANSI_END


class ColorsExtended:
    global ANSI_END
    initialize_ansi()

    CEND = ANSI_END
    CBOLD = '\33[1m'
    CITALIC = '\33[3m'
    CURL = '\33[4m'
    CBLINK = '\33[5m'
    CBLINK2 = '\33[6m'
    CSELECTED = '\33[7m'

    CBLACK = '\33[30m'
    CRED = '\33[31m'
    CGREEN = '\33[32m'
    CYELLOW = '\33[33m'
    CBLUE = '\33[34m'
    CVIOLET = '\33[35m'
    CBEIGE = '\33[36m'
    CWHITE = '\33[37m'

    CBLACKBG = '\33[40m'
    CREDBG = '\33[41m'
    CGREENBG = '\33[42m'
    CYELLOWBG = '\33[43m'
    CBLUEBG = '\33[44m'
    CVIOLETBG = '\33[45m'
    CBEIGEBG = '\33[46m'
    CWHITEBG = '\33[47m'

    CGREY = '\33[90m'
    CRED2 = '\33[91m'
    CGREEN2 = '\33[92m'
    CYELLOW2 = '\33[93m'
    CBLUE2 = '\33[94m'
    CVIOLET2 = '\33[95m'
    CBEIGE2 = '\33[96m'
    CWHITE2 = '\33[97m'

    CGREYBG = '\33[100m'
    CREDBG2 = '\33[101m'
    CGREENBG2 = '\33[102m'
    CYELLOWBG2 = '\33[103m'
    CBLUEBG2 = '\33[104m'
    CVIOLETBG2 = '\33[105m'
    CBEIGEBG2 = '\33[106m'
    CWHITEBG2 = '\33[107m'


class _RTL:
    # noinspection GrazieInspection
    """
    Tried to use the following, but it didn't work.
    This is here for reference only.
    If you want to use RTL, use:
        from bidi.algorithm import get_display
        message = get_display(message)
    Or use our 'print_api' functionality:
        atomicshop.print_api.print_api(message, rtl=True)


    Usage:
        print(f'{RTL.RTL_ISOLATE}שלום{RTL.RTL_POP_DIRECTIONAL_ISOLATE}')
    """
    # Put in the beginning of text.
    RTL_ISOLATE = u'\u2067'
    # Put in the end of the text.
    RTL_POP_DIRECTIONAL_ISOLATE = u'\u2069'

    # Better use the above, instead of the bottom. Could lead to problems: https://ideone.com/VOysHA
    # RTL_EMBEDDING = u'\u202B'
    # RTL_POP_DIRECTIONAL_FORMATTING = u'\u202C'

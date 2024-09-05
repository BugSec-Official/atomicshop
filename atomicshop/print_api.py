import sys
import logging

from .basics import ansi_escape_codes
from .basics import tracebacks


def print_api(
        message: any,
        color: any = None,
        print_end: str = '\n',
        rtl: bool = False,
        error_type: bool = False,
        logger: logging.Logger = None,
        logger_method: str = 'info',
        stdout: bool = True,
        stderr: bool = True,
        stdcolor: bool = True,
        traceback_string: bool = False,
        oneline: bool = False,
        oneline_end: str = '',
        **kwargs: object) -> None:
    """
    Function of custom api that is responsible for printing messages to console.
    By default, the 'logger' is 'None', meaning regular 'print' function will be used.
    If it is passed, then it will be used to output messages and not the 'print' function.

    Usage in functions:
        The parameter to pass all the arguments to this is 'print_kwargs'.
        Example:
            def some_function(print_kwargs: dict = None):
                if not print_kwargs:
                    print_kwargs = dict()

        The description of this argument in the function should be:
            :param print_kwargs: dict, that contains all the arguments for 'print_api' function.

        Then, in the function, you can use it like this:
            print_api(message, **print_kwargs)
            # If 'print_kwargs' is 'None'.
            print_api(message, **(print_kwargs or {}))
            print_api(message, print_kwargs=print_kwargs)
            print_api(message, print_kwargs={'logger': self.logger})

    :param message: Message that will be printed to console. Doesn't have to be string - can be 'any'.
    :param color: color of message to print.
    :param print_end: string, that sets 'end' method for print function. Since, this is not available for loggers,
        and it is much harder to implement in multithreading environment. Currently tested values are:
            '\r': print on the same line and remove previous.
    :param rtl: boolean, that sets Right-To-Left printing. If you see unreadable characters in your terminal / CMD,
        you need to set default font in properties that supports your language. 'Courier New' should be fine.
    :param error_type: Boolean that sets if the 'message' parameter that was passed would act as 'error'.
        Meaning, that if 'stderr=False', this 'message' won't be displayed.
    :param logger: Logger object that has methods like '.info()', '.error().
    :param logger_method: Method of the logger passed as string. Example: 'info', 'error'.
    :param stdout: Boolean that sets if the program should output regular prints or not.
    :param stderr: Boolean that sets if the program should output error/exception prints or not.
    :param stdcolor: Boolean that sets if the output should be colored or not.
    :param traceback_string: Boolean that sets if the program should print traceback of exceptions or not.
        If 'stderr' is set to 'False', this will be ignored.
    :param oneline: Boolean that sets if the program should output multiline message to oneline.
        This is needed in multithreaded script. There could be times when logger will output same message on several
        lines and these lines will be mixed with outputs from other threads.
    :param oneline_end: String that will be used to replace '\n' in 'message' if 'oneline' is set to 'True'.
    :return:
    """

    # param raise_exception: boolean, if we're inside exception, this sets whether exception should be raised or passed.
    #     Default is 'True' since this is the default in python.
    # param exit_on_error: Boolean that sets if the program should end on error/exception if 'error_type' is
    #     set to 'True'. 'exit_on_error' by default is set to 'False'.
    #     If you want script to exit, you need to specify 'True'.

    # Inner functions already get all the local variables of the main function.
    def print_or_logger():
        from .wrappers.loggingw import loggingw
        nonlocal message
        nonlocal color
        nonlocal traceback_string
        nonlocal error_type

        # This section takes care of different types of string manipulations for message.

        # If 'rtl' is set to 'True', we'll add Right-To-Left text conversion to 'message'.
        if rtl:
            # Lazy importing of 'bidi' library. It's not a problem since python caches the library after first import.
            # Off-course, it will be imported from the cache each time this section is triggered.
            # pip install python-bidi
            from bidi.algorithm import get_display
            message = get_display(message)

        if logger_method == 'error' or logger_method == 'critical':
            error_type = True

        # If exception was raised and 'stderr=True'.
        if sys.exc_info()[0] is not None and stderr and traceback_string:
            # If 'traceback' is set to 'True', we'll output traceback of exception.
            if traceback_string:
                if message:
                    message = f'{message}\n{tracebacks.get_as_string()}{message}'
                else:
                    message = tracebacks.get_as_string()

            color = 'red'

        # If 'stdcolor' is 'True', the console output will be colored.
        if stdcolor:
            # If 'logger.error' should be outputted to console, and 'color' wasn't selected, then set color to 'yellow'.
            if logger_method == 'error' and not color:
                color = 'yellow'
            # If 'logger.critical' should be outputted to console, and 'color' wasn't selected, then set color to 'red'.
            elif logger_method == 'critical' and not color:
                color = 'red'

            if color is not None and logger is None:
                message = ansi_escape_codes.get_colors_basic_dict(color) + message + ansi_escape_codes.ColorsBasic.END

        # If 'online' is set to 'True', we'll output message as oneline.
        if oneline:
            message = message.replace("\n", oneline_end)

        # ================================
        # This section outputs the message.

        # If logger passed.
        if logger:
            # Emit to logger only if 'print_end' is default, since we can't take responsibility for anything else.
            if print_end == '\n':
                if stdcolor and color is not None:
                    # Use logger to output message.
                    with loggingw.temporary_change_logger_stream_handler_emit_color(logger, color):
                        getattr(logger, logger_method)(message)
                else:
                    # Use logger to output message.
                    getattr(logger, logger_method)(message)
        # If logger wasn't passed.
        else:
            # Use print to output the message.
            print(message, end=print_end)

    # = Main Section with printing cases ===============================================================================
    # Convert message to string.
    message = str(message)

    # If we should print.
    if stdout and stderr:
        print_or_logger()
    elif stdout and not stderr:
        if not error_type:
            print_or_logger()
    elif not stdout and stderr:
        if error_type:
            print_or_logger()


def print_status(
        prefix_string: str,
        current_state,
        final_state=None,
        suffix_string: str = str(),
        same_line: bool = True,
        **kwargs):
    """
    The function will print specified variables in a specific format on the same line, based on 'same_line' parameter.

    :param prefix_string: string, will be printed before the status.
    :param current_state: numeric representation of current state.
    :param final_state: numeric representation of final state. Can be None. If so, the function will print only
        current state.
        Example: current_state / final_state, 1 / 10, 2 / 10, 3 / 10, etc.
    :param suffix_string: string, since the lines are printed on the same line, it can happen that one line can be
        longer than the other. If shorter line come after the longer one, it will align on top of the longer line.
    :param same_line: Boolean, if True, the lines will be printed on the same line, otherwise on different lines.

    Example:
        Line 1: 'Downloaded bytes: 100 / 1000'
        Line 2: 'Skipped Empty bytes: 200 / 1000'
        Line 3: 'Downloaded bytes: 300 / 1000000'
        Since line 3 is shorter than line 2, it will align on top of line 2.
        So, to avoid this, we can add a suffix string with empty spaces to line 3:
        print_status(
            prefix_string='Downloaded bytes', current_state=300, final_state=1000, suffix_string='    ', same_line=True)
        This will add 4 empty spaces to the end of line 3:
        Line 2: 'Skipped Empty bytes: 200 / 1000'
        Line 3: 'Downloaded bytes: 300 / 1000    '
    :param kwargs: keyword arguments to pass to 'print_api' function.
    :return: None
    """

    if final_state:
        message = f'{prefix_string}{current_state} / {final_state}{suffix_string}'
    else:
        message = f'{prefix_string}{current_state}{suffix_string}'

    if same_line:
        print_api(message, print_end='\r', **kwargs)
    else:
        print_api(message, **kwargs)


def print_status_of_list(
        list_instance: list,
        prefix_string: str,
        current_state,
        suffix_string: str = str(),
        same_line: bool = True,
        **kwargs):
    """
    The function will print specified variables in a specific format on the same line, based on 'same_line' parameter.

    :param list_instance: list, the list that will be used to get the final state. Since we want last item in the list,
        to be printed with regular 'print_end' parameter and not '\r', we need to get the last item in the list.
    :param prefix_string: string, will be printed before the status.
    :param current_state: numeric representation of current state.
    :param suffix_string: string, since the lines are printed on the same line, it can happen that one line can be
        longer than the other. If shorter line come after the longer one, it will align on top of the longer line.
    :param same_line: Boolean, if True, the lines will be printed on the same line (but not the last line),
        otherwise on different lines.

    For example check the 'print_status' function.

    :param kwargs: keyword arguments to pass to 'print_api' function.
    :return: None
    """

    final_state = len(list_instance)

    if same_line:
        if current_state != final_state:
            same_line = True
        else:
            same_line = False

    print_status(prefix_string=prefix_string, current_state=current_state, final_state=final_state,
                 suffix_string=suffix_string, same_line=same_line, **kwargs)

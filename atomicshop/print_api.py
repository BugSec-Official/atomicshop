# v1.1.0 - 21.03.2023 16:40
from .basics.ansi_escape_codes import ColorsBasic, get_colors_basic_dict


# noinspection PyUnusedLocal
def print_api(message: any,
              color: any = None,
              print_end: str = '\n',
              rtl: bool = False,
              error_type: bool = False,
              logger: object = None,
              logger_method: str = 'info',
              stdout: bool = True,
              stderr: bool = True,
              stdcolor: bool = True,
              # raise_exception: bool = True,
              # exit_on_error: bool = False,
              oneline_exceptions: bool = False,
              **kwargs: object) -> None:
    """
    Function of custom api that is responsible for printing messages to console.
    By default, the 'logger' is 'None', meaning regular 'print' function will be used.
    If it is passed, then it will be used to output messages and not the 'print' function.

    :param message: Message that will be printed to console. Doesn't have to be string - can be 'any'.
    :param color: color of message to print.
    :param print_end: string, that sets 'end' method for print function. Since, this is not available for loggers,
        and it is much harder to implement in multithreading environment. Currently supported:
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
    :param raise_exception: boolean, if we're inside exception, this sets whether exception should be raised or passed.
        Default is 'True' since this is the default in python.
    :param exit_on_error: Boolean that sets if the program should end on error/exception if 'error_type' is
        set to 'True'. 'exit_on_error' by default is set to 'False'.
        If you want script to exit, you need to specify 'True'.
    :param oneline_exceptions: Boolean that sets if the program should print exceptions as oneline or not.
        This is needed in multithreaded script. There could be times when logger will output same message on several
        lines and these lines will be mixed with outputs from other threads.
    :return:
    """

    # Inner functions already get all the local variables of the main function.
    def print_or_logger():
        nonlocal message
        nonlocal color

        # This section takes care of different types of string manipulations for message.

        # If 'exit_on_error' is set to 'True', we'll add 'exit_message' on new line after 'message'.
        # if error_type and exit_on_error and raise_exception:
        #     message = message + '\n' + exit_message

        # If 'rtl' is set to 'True', we'll add Right-To-Left text conversion to 'message'.
        if rtl:
            # Lazy importing of 'bidi' library. It's not a problem since python caches the library after first import.
            # Off-course, it will be imported from the cache each time this section is triggered.
            # pip install python-bidi
            from bidi.algorithm import get_display
            message = get_display(message)

        # If 'stdcolor' is 'True', the console output will be colored.
        if stdcolor:
            # If 'logger.error' should be outputted to console, and 'color' wasn't selected, then set color to 'yellow'.
            if logger_method == 'error' and not color:
                color = 'yellow'
            # If 'logger.critical' should be outputted to console, and 'color' wasn't selected, then set color to 'red'.
            elif logger_method == 'critical' and not color:
                color = 'red'

            if color:
                message = get_colors_basic_dict(color) + message + ColorsBasic.END

        # ================================
        # This section outputs the message.

        # If logger passed.
        if logger:
            # Emit to logger only if 'print_end' is default, since we can't take responsibility for anything else.
            if print_end == '\n':
                # Use logger to output message.
                getattr(logger, logger_method)(message)
        # If logger wasn't passed.
        else:
            # Use print to output the message.
            print(message, end=print_end)

    # = Main Section with printing cases ===============================================================================
    # exit_message: str = 'Exiting...'

    # If we should print.
    if stdout and stderr:
        print_or_logger()
    elif stdout and not stderr:
        if not error_type:
            print_or_logger()
    elif not stdout and stderr:
        if error_type:
            print_or_logger()

    # ==================================
    # This section is responsible for ending the script.

    # Check if we're inside exception. In this case each of 3 entries in 'sys.exc_info()' tuple will not equal
    # to 'None', so picked only the first one.
    # if sys.exc_info()[0] and not exit_on_error:
    #     # If 'raise_exception' is set to 'True', we'll end the script with exception.
    #     if pass_exception:
    #         pass

    # If 'exit_on_error' is set to 'True', we'll end the script.
    # if exit_on_error and error_type:
    #     sys.exit()

# v1.0.2 - 21.03.2023 16:40
import inspect


def get_target_function_default_args_and_combine_with_current(function_name, *args, **kwargs):
    # Usage:
    # args, kwargs = get_target_function_default_args_and_combine_with_current(function_name, *args, **kwargs)

    # The problem with decorators, or when passing functions as arguments, while using *args, **kwargs,
    # we can see only the arguments that were passed to the function explicitly, but not the
    # arguments that are set as default in the function itself.
    # Default arguments in the function definition:
    # def function_name(message: str, setting: bool, error_type: bool = True)
    # Usage:
    # function_name(message='test message', setting=True)
    # In the example above we will see kwargs as:
    # kwargs = {'message': 'test message', 'setting': True}
    # Meaning we will not see the default variable that is set in the function:
    # {'error_type': True}

    # Fix:
    # Get default arguments signature from passed function.
    default_signature = inspect.signature(function_name)
    # Get current arguments that were passed to the decorator.
    bound = default_signature.bind(*args, **kwargs)
    # Apply the default arguments that are set in the function.
    bound.apply_defaults()
    # Exchanging the default kwargs with the fetched ones.
    kwargs = bound.arguments
    # args can be nullified if you already have everything in 'kwargs'.
    args = ()

    # Now if we have 'kwargs' passed we need to fetch them too.
    kwargs.update(kwargs['kwargs'])
    # We can remove 'kwargs' key inside 'kwargs' dict.
    try:
        del kwargs['kwargs']
    # If the key doesn't exist, continue.
    except KeyError:
        pass

    return args, kwargs


def get_api_commands_list() -> list:
    return ['logger', 'logger_method', 'stdout', 'stderr', 'exit_on_error']


def get_parent_caller_arguments():
    # Since this function is being called by the function that want to know its function's caller arguments
    # we need to execute 'f_back' method twice.
    # First 'f_back' of the previous function and the second of the caller function that we're interested in.
    previous_frame = inspect.currentframe().f_back.f_back
    # Get all the arguments and values of that frame. This is including all the arguments that were passed to the
    # function and also its locals.
    # To use only the arguments that were passed to the function:
    # previous_frame_args.args
    # To show only the locals:
    # previous_frame_args.locals
    # Getting the values of the passed keys:
    # for arg in previous_frame_args.args:
    #    value = previous_frame_args.locals[arg]
    # Get dictionary with args keys and values (but if some values are none, you will get an exception):
    # inspect.formatargvalues(previous_frame_args)
    previous_frame_args = inspect.getargvalues(previous_frame)

    # Get dictionary of keys and values of passed arguments.
    args_dictionary: dict = dict()

    # If the frame was regular function, then we'll get the 'args' list and iterate through it against the 'locals'
    # in order to get its values.
    if previous_frame_args.args:
        for arg in previous_frame_args.args:
            value = previous_frame_args.locals[arg]
            args_dictionary.update({arg: value})
    # If the variables were passed as 'kwargs', then we'll get the 'kwargs' dictionary directly from 'locals'.
    elif previous_frame_args.locals['kwargs']:
        args_dictionary = previous_frame_args.locals['kwargs']

    return args_dictionary


# noinspection GrazieInspection
def get_missing_arguments(function_name, api: bool = False):
    """
    Usage:
        from functions_custom_api import get_missing_arguments
        def print_something(print_output=False):
            function_name(message=f'Reading file: {file_path}', **get_missing_arguments(function_name))
    When invoking a function, you need to pass its reference to 'get_missing_arguments' function as input as well.

    Two asterisks (**) unpack the dictionary object that the function return, so all the keys and values are passed
    as is.

    While using this function, you can't pass same arguments twice.
    Example:
        from functions_custom_api import get_missing_arguments
        def print_something(print_output=False):
            function_name(message=f'Reading file: {file_path}',
                          print_output=True,
                          **get_missing_arguments(function_name))

    You will get an error:
        TypeError: classes.functions_custom_api.function_name() got multiple values for keyword argument 'print_output'

    The right way to do it if you want to change the value of 'print_output':
        from functions_custom_api import get_missing_arguments
        def print_something(print_output=False):
            print_output=True
            function_name(message=f'Reading file: {file_path}', **get_missing_arguments(function_name))

    This is because we get the value of the argument from 'locals' of the function.

    :param function_name: name of the target function to check the required arguments.
    :param api: boolean that sets if the function will pass only the api related arguments.
    :return: dict
    """

    def update_final_dictionary():
        value = previous_frame_args.locals[arg]
        final_dictionary.update({arg: value})

    # Get frame of the previous parent calling function.
    previous_frame = inspect.currentframe().f_back
    # Get all the arguments and values of that frame. This is including all the arguments that were passed to the
    # function and also its locals.
    # To use only the arguments that were passed to the function:
    # previous_frame_args.args
    # To show only the locals:
    # previous_frame_args.locals
    # Getting the values of the passed keys:
    # for arg in previous_frame_args.args:
    #    value = previous_frame_args.locals[arg]
    previous_frame_args = inspect.getargvalues(previous_frame)

    # Get all the required arguments of target function.
    target_function_required_args = list()
    for x, p in inspect.signature(function_name).parameters.items():
        if x in previous_frame_args.args:
            # if p.default == inspect.Parameter.empty and p.kind != inspect.Parameter.VAR_POSITIONAL:
            target_function_required_args.append(x)

    final_dictionary: dict = dict()
    for arg in target_function_required_args:
        if not api:
            update_final_dictionary()
        else:
            if arg in get_api_commands_list():
                update_final_dictionary()

    return final_dictionary


"""
# 'print_api' usage with inspect module functions.
def print_api(message,
              error_type: bool = False,
              logger=None,
              logger_method: str = 'info',
              stdout: bool = True,
              stderr: bool = True,
              exit_on_error: bool = False,
              override_argument_fetching: bool = False):
    """
"""
    Function of custom api that is responsible for printing messages to console.
    By default, the 'logger' is 'None', meaning regular 'print' function will be used.
    If it is passed, then it will be used to output messages and not the 'print' function.

    Example of overriding fetched arguments:
        print_api(message='Regular message', stdout=False, stderr=True, override_argument_fetching=True)

    :param message: Message that will be printed to console. Doesn't have to be string. Can be 'any'.
    :param error_type: Boolean that sets if the 'message' parameter that was passed would act as 'error'.
        Meaning, that if 'stderr=False', this 'message' won't be displayed.
    :param logger: Logger object that has methods like '.info()', '.error().
    :param logger_method: Method of the logger passed as string. Example: 'info', 'error'.
    :param stdout: Boolean that sets if the program should output regular prints or not.
    :param stderr: Boolean that sets if the program should output error/exception prints or not.
    :param exit_on_error: Boolean that sets if the program should end on error/exception.
        'exit_on_error' by default is set to 'False', this is to show the script engineers that if they want a function
        to end script execution, they need to do it explicitly, since it will be seen from the place where the function
        is executed from that the function will end the script on errors.
    :param override_argument_fetching: Boolean that sets if the program should fetch arguments from parent calling
        function (previous function) or not.
    :return:
    """
"""
    # Inner functions already get all the local variables of the main function.
    def print_or_logger_with_exit():
        # If logger passed.
        if logger:
            # Use logger to output message.
            getattr(logger, logger_method)(message)
            # If we should exit.
            if exit_on_error and error_type:
                # Use logger to output that message and exit.
                getattr(logger, logger_method)(exit_message)
                sys.exit()
        # If logger wasn't passed.
        else:
            # Use print to output the message.
            print(message)
            # If we should exit.
            if exit_on_error and error_type:
                # Print the exit message and exit.
                print(exit_message)
                sys.exit()

    # Section that is responsible for fetching variables from the calling function =====================================
    # If 'override_argument_fetching' is 'True', we will fetch the arguments from previous function.
    if not override_argument_fetching:
        args_dictionary = get_parent_caller_arguments()

        # Unfortunately there is no way to modify 'locals()' in a function, so each variable needs to be checked
        # explicitly.
        if 'logger' in args_dictionary.keys():
            logger = args_dictionary['logger']
        if 'logger_method' in args_dictionary.keys():
            logger_method = args_dictionary['logger_method']
        if 'stdout' in args_dictionary.keys():
            stdout = args_dictionary['stdout']
        if 'stderr' in args_dictionary.keys():
            stderr = args_dictionary['stderr']
        if 'exit_on_error' in args_dictionary.keys():
            exit_on_error = args_dictionary['exit_on_error']
    # = EOF Fetching variables section =================================================================================
    # = Main Section with printing cases ===============================================================================
    exit_message: str = 'Exiting...'

    # If we should print.
    if stdout and stderr:
        print_or_logger_with_exit()
    elif stdout and not stderr:
        if not error_type:
            print_or_logger_with_exit()
    elif not stdout and stderr:
        if error_type:
            print_or_logger_with_exit()
    # If we shouldn't print.
    else:
        # Should we exit?
        if exit_on_error: sys.exit()
        # if exit_on_error:
        #     sys.exit()

"""
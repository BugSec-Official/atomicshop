from ... import diff_check
from ...print_api import print_api
from .hash_checks import file, url


DIFF_CHECKER = diff_check.DiffChecker(
    return_first_cycle=False,
    operation_type='single_object'
)


def setup_check(change_monitor_instance):
    change_monitor_instance.set_input_file_path()

    if change_monitor_instance.object_type == 'file':
        file.setup_check(change_monitor_instance, change_monitor_instance.check_object)
    elif 'url_' in change_monitor_instance.object_type:
        url.setup_check(change_monitor_instance, change_monitor_instance.check_object)


def execute_cycle(change_monitor_instance, print_kwargs: dict = None):
    """
    This function executes the cycle of the change monitor: hash.

    :param change_monitor_instance: Instance of the ChangeMonitor class.
    :param print_kwargs: print_api kwargs.

    :return: List of dictionaries with the results of the cycle.
    """

    if print_kwargs is None:
        print_kwargs = dict()

    return_list = list()

    if change_monitor_instance.object_type == 'file':
        # Get the hash of the object.
        file.get_hash(change_monitor_instance, change_monitor_instance.check_object, print_kwargs=print_kwargs)
    elif 'url_' in change_monitor_instance.object_type:
        # Get the hash of the object.
        url.get_hash(change_monitor_instance, change_monitor_instance.check_object, print_kwargs=print_kwargs)

    # Check if the object was updated.
    result, message = change_monitor_instance.diff_checker.check_string(
        print_kwargs=print_kwargs)

    # If the object was updated, print the message in yellow color, otherwise print in green color.
    if result:
        print_api(message, color='yellow', **print_kwargs)
        # create_message_file(message, self.__class__.__name__, logger=self.logger)

        return_list.append(message)
    else:
        print_api(message, color='green', **print_kwargs)

    return return_list

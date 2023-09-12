from ...print_api import print_api
from .hash_checks import file, url


def _execute_cycle(change_monitor_instance, print_kwargs: dict = None):
    """
    This function executes the cycle of the change monitor: hash.

    :param change_monitor_instance: Instance of the ChangeMonitor class.

    :return: List of dictionaries with the results of the cycle.
    """

    if print_kwargs is None:
        print_kwargs = dict()

    return_list = list()
    # Loop through all the objects to check.
    for check_object_index, check_object in enumerate(change_monitor_instance.check_object_list):
        if change_monitor_instance.object_type == 'file':
            # Get the hash of the object.
            file.get_hash(change_monitor_instance, check_object_index, check_object, print_kwargs=print_kwargs)
        elif 'url_' in change_monitor_instance.object_type:
            # Get the hash of the object.
            url.get_hash(change_monitor_instance, check_object_index, check_object, print_kwargs=print_kwargs)

        if change_monitor_instance.first_cycle:
            # Set the input file path.
            change_monitor_instance._set_input_file_path(check_object_index=check_object_index)

        # Check if the object was updated.
        result, message = change_monitor_instance.diff_check_list[check_object_index].check_string(
            print_kwargs=print_kwargs)

        # If the object was updated, print the message in yellow color, otherwise print in green color.
        if result:
            print_api(message, color='yellow', **print_kwargs)
            # create_message_file(message, self.__class__.__name__, logger=self.logger)

            return_list.append(message)
        else:
            print_api(message, color='green', **print_kwargs)

    return return_list

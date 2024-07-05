from .... import filesystem, hashing


def setup_check(change_monitor_instance, check_object: str):
    original_name: str = str()

    # If 'generate_input_file_name' is True, or 'store_original_object' is True, we need to create a
    # filename without extension.
    if change_monitor_instance.store_original_object or change_monitor_instance.generate_input_file_name:
        # Get the last directory from the url.
        original_name = filesystem.get_file_name(check_object)
        # Make characters lower case.
        original_name = original_name.lower()

    # If 'store_original_object' is True, then we need to create a filepath to store.
    if change_monitor_instance.original_object_directory:
        # Add extension to the file name.
        original_file_name = original_name

        # Make path for original object.
        change_monitor_instance.original_object_file_path = filesystem.add_object_to_path(
            change_monitor_instance.original_object_directory, original_file_name)

    if change_monitor_instance.generate_input_file_name:
        # Remove dots from the file name.
        original_name_no_dots = original_name.replace('.', '-')
        # Make path for 'input_file_name'.
        change_monitor_instance.input_file_name = f'{original_name_no_dots}.txt'

    # Change settings for the DiffChecker object.
    change_monitor_instance.diff_checker.return_first_cycle = False

    change_monitor_instance.diff_checker.check_object_display_name = \
        f'{original_name}|{change_monitor_instance.object_type}'


def get_hash(change_monitor_instance, check_object: str, print_kwargs: dict = None):
    """
    The function will get the hash of the URL content.

    :param change_monitor_instance: Instance of the ChangeMonitor class.
    :param check_object: string, full URL to a web page.
    :param print_kwargs: dict, that contains all the arguments for 'print_api' function.
    """

    # Copy the file to the original object directory.
    if change_monitor_instance.original_object_file_path:
        filesystem.copy_file(check_object, change_monitor_instance.original_object_file_path)

    # Get hash of the file.
    hash_string = hashing.hash_file(check_object)

    # Set the hash string to the 'check_object' variable.
    change_monitor_instance.diff_checker.check_object = hash_string

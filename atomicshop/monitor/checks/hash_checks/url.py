from .... import filesystem, hashing, urls


def get_hash(change_monitor_instance, check_object_index: int, check_object: str, print_kwargs: dict = None):
    """
    The function will get the hash of the URL content.

    :param change_monitor_instance: Instance of the ChangeMonitor class.
    :param check_object_index: integer, index of the object in the 'check_object_list' list.
    :param check_object: string, full URL to a web page.
    :param print_kwargs: dict, that contains all the arguments for 'print_api' function.
    """
    # Extract the method name from the object type.
    get_method = change_monitor_instance.object_type.split('_', 1)[1]

    # If this is the first cycle, we need to set several things.
    if change_monitor_instance.first_cycle:
        original_name: str = str()

        # If 'generate_input_file_name' is True, or 'store_original_object' is True, we need to create a
        # filename without extension.
        if change_monitor_instance.store_original_object or change_monitor_instance.generate_input_file_name:
            # Get the last directory from the url.
            original_name = urls.url_parser(check_object)['directories'][-1]
            # Make characters lower case.
            original_name = original_name.lower()

        # If 'store_original_object' is True, then we need to create a filepath to store.
        extension = None
        if change_monitor_instance.original_object_directory:
            # Add extension to the file name.
            if 'playwright' in get_method:
                extension = get_method.split('_')[1]
            elif get_method == 'urllib':
                extension = 'html'
            original_file_name = f'{original_name}.{extension}'

            # Make path for original object.
            change_monitor_instance.original_object_file_path = filesystem.add_object_to_path(
                change_monitor_instance.original_object_directory, original_file_name)

        if change_monitor_instance.generate_input_file_name:
            # Make path for 'input_file_name'.
            change_monitor_instance.input_file_name = f'{original_name}.txt'

        # Change settings for the DiffChecker object.
        change_monitor_instance.diff_check_list[check_object_index].return_first_cycle = False

        change_monitor_instance.diff_check_list[check_object_index].check_object_display_name = \
            f'{original_name}|{change_monitor_instance.object_type}'

    # Get hash of the url. The hash will be different between direct hash of the URL content and the
    # hash of the file that was downloaded from the URL. Since the file has headers and other information
    # that is not part of the URL content. The Original downloaded file is for reference only to see
    # what was the content of the URL at the time of the download.
    hash_string = hashing.hash_url(
        check_object, get_method=get_method, path=change_monitor_instance.original_object_file_path,
        print_kwargs=print_kwargs
    )

    # Set the hash string to the 'check_object' variable.
    change_monitor_instance.diff_check_list[check_object_index].check_object = hash_string

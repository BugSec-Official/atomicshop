from pathlib import Path
from typing import Union

from .file_io import file_io, jsons
from .print_api import print_api
from .basics import list_of_dicts


class DiffChecker:
    """
    This class is used to check if an object changed since last time.
    If there was change, dict is returned containing: the object, old state, updated state and type of object.
        In addition, a general string message is returned.
    If the object didn't change, it will return None and a message.
    The object can be anything: file, directory, process, etc.
    You will need to execute appropriate function to check the object.
    Example: if you want to check if a file was updated, you will need to execute 'check_hash_file' function.
    You can also specify a directory for storing input files for current state of objects,
    to check later if this state isn't updated.
    You don't have to use input file to store queried content, you can store it in memory only. Off course, it will
    be lost if the script is restarted.
    """

    def __init__(
            self,
            check_object: any = None,
            check_object_display_name: str = None,
            aggregation: bool = False,
            input_file_path: str = None,
            input_file_write_only: bool = True,
            return_first_cycle: bool = True
    ):
        """
        :param check_object: any, object to check if it changed.
            You will need to execute appropriate function to check the object.
            Example: if you want to check if a string was updated, you will need to execute 'check_string' function.

            The object is 'None' by default, since there are objects that are needed to be provided in the
            function input for that object. So, not always you know what your object type during class initialization.
        :param check_object_display_name: string, name of the object to display in the message.
            If not specified, the 'check_object' will be displayed.
        :param aggregation: boolean, if True, the object will be aggregated with other objects in the list of objects.
            Meaning, that the object will be checked against the existing objects in the list, and if it is not
            in the list, it will be added to the list. If it is in the list, it will be ignored.
        :param input_file_path: string, full file path for storing input file for current state of objects,
            to check later if this state isn't updated. If this variable is left empty, all the content will be saved
            in memory and input file will not be used.

            If the file is not specified, the update of an object will be checked
            only during the time that the script is running. Meaning, each time the script starts from beginning
            it will measure the object from the start as the script didn't know what it was before running.
            The problem? If you want to check that a program updated and the computer restarted, you will not
            know about that if the input file wasn't written. Since, the script will not know what happened before
            restart and what hash value the file had before the update.
        :param input_file_write_only: boolean,
            True: each time there is an update in the data, the input file will be written with new data, but
                the reading of old data will be from memory (the old data will not be read from the file).
            False: Read old data from the input file and then write the new data if there is an update.
        :param return_first_cycle: boolean, the first cycle is the one that compares acquired content to empty
            content, since there was no content previously. Meaning, that content was updated, but it's not
            always interesting - the content didn't really update, it just didn't exist.

            True: return updated dictionary on first cycle. This is the default.
            False: don't return updated dictionary on first cycle.
        """

        # 'check_object' can be none, so checking if it not equals empty string.
        if check_object == "":
            raise ValueError("[check_object] option can't be empty string.")

        self.check_object = check_object
        self.check_object_display_name = check_object_display_name
        self.aggregation: bool = aggregation
        self.input_file_path: str = input_file_path
        self.input_file_write_only: bool = input_file_write_only
        self.return_first_cycle: bool = return_first_cycle

        if not self.check_object_display_name:
            self.check_object_display_name = self.check_object

        # Previous content.
        self.previous_content: Union['list', 'str', None] = None
        # The format the file will be saved as (not used as extension): txt, json.
        self.save_as: str = str()

    def check_string(self, print_kwargs: dict = None):
        """
        The function will check file content for change by hashing it and comparing the hash.
        """

        if not isinstance(self.check_object, str):
            raise TypeError(f"[check_object] must be string, not {type(self.check_object)}.")

        self.save_as = 'txt'

        # Each function need to initialize the object content to the proper type it will use.
        if not self.previous_content:
            self.previous_content = str()

        return self._handle_input_file(print_kwargs=print_kwargs)

    def check_list_of_dicts(self, sort_by_keys: list = None, print_kwargs: dict = None):
        """
        The function will check list of dicts for change, while saving it to combined json file.

        :param sort_by_keys: list, of keys to sort the list of dicts by.
        :param print_kwargs: dict, of kwargs to pass to 'print_api' function.
        """

        if not isinstance(self.check_object, list):
            raise TypeError(f'[check_object] must be list, not {type(self.check_object)}.')

        self.save_as = 'json'

        # Each function need to initialize the object content to the proper type it will use.
        if not self.previous_content:
            self.previous_content = list()

        return self._handle_input_file(sort_by_keys, print_kwargs=print_kwargs)

    def _handle_input_file(self, sort_by_keys, print_kwargs: dict = None):
        # If 'input_file_path' was specified, this means that the input file will be created for storing
        # content of the function to compare.
        if self.input_file_path:
            # If 'previous_content' is not yet probed, meaning that this is the first cycle and since 'use_input_file'
            # was set 'True', we will read the input file to get the previously probed content.
            # Also, if the user specified 'input_file_write_only=False' that he doesn't want to only write the
            # input file, we will read the file in the beginning of each cycle.
            if not self.previous_content or not self.input_file_write_only:
                try:
                    if self.save_as == 'txt':
                        self.previous_content = file_io.read_file(
                            self.input_file_path, stderr=False, **print_kwargs)
                    elif self.save_as == 'json':
                        self.previous_content = jsons.read_json_file(
                            self.input_file_path, stderr=False, **print_kwargs)
                except FileNotFoundError as except_object:
                    message = f"Input File [{Path(except_object.filename).name}] doesn't exist - Will create new one."
                    print_api(message, color='yellow', **print_kwargs)
                    pass

        current_content = list(self.check_object)

        # If known content differs from just taken content.
        result = None
        message = f'First Cycle on Object: {self.check_object_display_name}'

        if self.aggregation:
            return self._aggregation_handling(current_content, result, message, sort_by_keys=sort_by_keys, print_kwargs=print_kwargs)
        else:
            return self._non_aggregation_handling(current_content, result, message, print_kwargs=print_kwargs)

    def _aggregation_handling(self, current_content, result, message, sort_by_keys, print_kwargs):
        if current_content[0] not in self.previous_content:
            # If known content is not empty (if it is, it means it is the first iteration, and we don't have the input
            # file, so we don't need to update the 'result', since there is nothing to compare yet).
            if self.previous_content or (not self.previous_content and self.return_first_cycle):
                result = {
                    'object': self.check_object_display_name,
                    'old': list(self.previous_content),
                    'updated': current_content
                    # 'type': self.object_type
                }

                # f"Type: {result['type']} | "
                message = f"Object: {result['object']} | Old: {result['old']} | Updated: {result['updated']}"

            # Make known content the current, since it is updated.
            self.previous_content.extend(current_content)

            # Sort list of dicts by specified list of keys.
            if sort_by_keys:
                self.previous_content = list_of_dicts.sort_by_keys(
                    self.previous_content, sort_by_keys, case_insensitive=True)

            # If 'input_file_path' was specified by the user, it means that we will use the input file to save
            # our known content there for next iterations to compare.
            if self.input_file_path:
                if self.save_as == 'txt':
                    # noinspection PyTypeChecker
                    file_io.write_file(self.previous_content, self.input_file_path, **print_kwargs)
                elif self.save_as == 'json':
                    jsons.write_json_file(
                        self.previous_content, self.input_file_path, use_default_indent=True, **print_kwargs)
        else:
            message = f"Object didn't change: {self.check_object_display_name}"

        return result, message

    def _non_aggregation_handling(self, current_content, result, message, print_kwargs):
        if self.previous_content != current_content:
            # If known content is not empty (if it is, it means it is the first iteration, and we don't have the input
            # file, so we don't need to update the 'result', since there is nothing to compare yet).
            if self.previous_content or (not self.previous_content and self.return_first_cycle):
                result = {
                    'object': self.check_object_display_name,
                    'old': self.previous_content,
                    'updated': current_content,
                    # 'type': self.object_type
                }

                # f"Type: {result['type']} | "
                message = f"Object: {result['object']} | Old: {result['old']} | Updated: {result['updated']}"

            # Make known content the current, since it is updated.
            self.previous_content = current_content

            # If 'input_file_path' was specified by the user, it means that we will use the input file to save
            # our known content there for next iterations to compare.
            if self.input_file_path:
                if self.save_as == 'txt':
                    # noinspection PyTypeChecker
                    file_io.write_file(self.previous_content, self.input_file_path, **print_kwargs)
                elif self.save_as == 'json':
                    jsons.write_json_file(
                        self.previous_content, self.input_file_path, use_default_indent=True, **print_kwargs)
        else:
            message = f"Object didn't change: {self.check_object_display_name}"

        return result, message

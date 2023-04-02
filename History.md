<!-- HISTORY -->
## History

* 1.6.5 - 02.04.2023
  * Added 'basics.list_to_dicts.is_value_exist_in_key' function.
* 1.6.4 - 02.04.2023
  * Renamed 'process_wrapper_curl.py' to '_process_wrapper_curl.py'
  * Renamed 'process_wrapper_tar.py' to '_process_wrapper_tar.py'
  * 'tempfiles' - converted some functions to private.
  * 'print_api.print_status' - added functionality for empty 'final_state' parameter.
  * Created 'sound.StereoMixRecorder' class for enhanced recording capabilities.
  * Added some python libraries as dependencies to be installed automatically.
* 1.6.3 - 31.03.2023
  * Fixed API references in modules added in 1.6.2.
* 1.6.2 - 31.03.2023
  * Added 'wrappers.numpyw' module.
  * Added 'wrappers.ffmpegw' module.
  * Added 'speech_recognize' module.
  * Added 'console_output' module.
  * Added 'appointment_management' module.
  * Added 'question_answer_engine' module.
  * Added 'print_status' function to 'print_api' module
* 1.6.1 - 31.03.2023
  * Added 'sound' module.
* 1.6.0 - 30.03.2023
  * csvs, jsons, file_io - moved to 'file_io' folder.
  * argparse_template, exceptions, guids, list_of_dicts, threads - moved to 'basic' folder.
  * 'update_checker.UpdateChecker' renamed to 'diff_check.DiffChecker' and moved to 'diff_check' folder.
  * 'diff_check.check_file_hash' renamed to 'diff_check.check_hash_file'.
  * 'web.check_is_status_ok' renamed to 'web.is_status_ok'.
  * 'hashing.file_hash' renamed to 'hashing.hash_file'.
  * Added used 'USER_AGENTS' dict to 'web'. This will not include ALL User Agents, but the ones I use.
  * Added 'get_page_bytes' function to 'web'.
  * Added 'hash_bytes' function to 'hashing'.
  * Added 'hash_url' function to 'hashing'.
  * Added 'get_list_of_directories_in_file_path' function to 'filesystem'.
  * Added 'contains_letter' function to 'strings'.
  * Added 'check_url' function to 'diff_check.DiffChecker'.
  * 'diff_check.DiffChecker.check_hash_file' - now generates input file name if not specified.
  * 'diff_check.handle_input_file' - now returns queried object and general string output message in dict as well.
  * 'clones.certauth' - styling fixes and mutable default argument fixes.
* 1.5.1 - 28.03.2023
  * Initial release

<h1 align="center">Atomic Workshop</h1>



<!-- ABOUT THE PROJECT -->
## About The Project

Atomic Workshop is python's library that was built by Denis Kras under Bugsec's roof.

The main purpose of the library is to simplify the process of developing under python.
The library is constantly being improved and supplemented with new features.
"Atomic" is a key to basic functions that a developer needs in his daily tasks: create directory, iterate over files, read/write files, manipulate lists, dicts, etc.

There are many gems hidden in the library:
* atomicshop.print_api: this is the main feature of this library. It allows you to print colored text, with different styles, with / without stdout / stderr, RTL text, logger usage. The API will be integrated in every function of the library in the future, so you can easily use it controlling outputs.
* atomicshop.etw.etw: Windows ETW - Event Tracing, a wrapper for FireEye project's ETW library with much easier API. Since, FireEye didn't update their library for quite a while, maybe another solution will be considered in the future. If you have suggestions, please let me know.
* atomicshop.etw.dns_trace: Windows DNS Event Tracing, Traces DNS requests / responses (Event ID: 3008) on Windows OSes that support Event Tracing. Outputs the real domain (not CDN: AWS, GoogleCloud, Azure, etc) with PID. Process Name and Command Line can be retrieved by option. Currently, process info is CPU intensive.
* atomicshop.sockets: Socket wrapper, can be used to create a server or client and manipulate sockets with relatively easy API. Server tester available.
* atomicshop.mitm: MITM Proxy, allows you to create a TCP proxy server (works with SSL) that will intercept requests and responses. You can modify them, log them, etc. ReadMe to follow. Based on SocketWrapper.
* atomicshop.http_parser: parse HTTP requests and responses to dictionary.
* atomicshop.diff_check.diff_check.DiffChecker: helps on checking if pyhon object, a file or any other thing was updated between checks.
* atomicshop.gitHub_wrapper: easily download branches and latest releases from GitHub repositories.
* atomicshop.archiver: extract archives using options.
* atomicshop.wrappers.configparserw.ConfigParserWrapper: read / write config files to dict, converting string values to other formats (int, bool, list, list_of_ints, etc).
* atomicshop.wrappers.ffmpegw.FFmpegWrapper: wrapper for FFmpeg, allows you to convert files to other formats. Downloads latest compiled release of ffmpeg from GitHub, if it doesn't find one.
* atomicshop.sound: this module currently can record sound from Stereo mix to WAV file.
* atomicshop.process: Process wrapper, can be used to get live output from a console process, while it still runs. Execute process in new cmd window, etc.
* atomicshop.scheduling: Scheduler with threads, you can schedule a function to run periodically each 30 minutes (or any specified period of time) using threads (or not).
* atomicshop.timer: measures time passed from the point you start it using python API.
* atomicshop.web.download_with_urllib: File downloader with status.
* atomicshop.file_io: File csv / json / text reader / writer.
* atomicshop.filesystem: functions like, move / create folders, copy / delete files, etc.
* And many more...

Currently, for complete picture you'll have to check the files in the library. I tried my best with understandable naming and grouping convention.
Probably in the future docs generated by SPHINX will follow. Currently most of the functions have docstrings with usage and examples.

Most of the functions presented here are atomic, meaning you can use them almost in any project.
Also, most of the functions were written firstly to be readable and understandable, and secondly functional. In addition, optimization was a priority.
The above meaning that the functions provided are fast and easy to use.
Some functions are presented as example of how to do something, to lessen querying to Google, StackOverflow and alike.

Off course, some functions are complete mess in terms of code, speed and probably even logic, but their usefulness outline the cons.
And later on, they will be rewritten to be more efficient.

Since, it's a "one man" project, improvements and fixes of existing functions will take time, but you can send me suggestions and pull requests. I will try to respond as soon as time allows.
The project is considered pre-pre alpha on heavy features like socket wrapper, but basic functions are stable and can be used in production.
Since, it's pre-alpha API names and functionality can change.
Follow project's change history for the latest. 

I tried my best to use as less external libraries as possible, but some of them are required.
The list of required libraries will follow, but for now - test to see what may be missing. I don't want for libraries to be requirements, since these libraries usage depend on your needs. 

Currently, the library is being developed on Windows 10 and python 3.10. No other platforms or python versions were tested.
Most of the features will work, but some require at least version 3.10, like SocketWrapper. Since, some features in it are 3.10 specific.
In June 2023, I will be moving to python 3.11.4 when it comes out and official support will move to that version as well.

The library and its features will evolve based on my curiosity and needs. But as of now, the updates to features list are almost on daily basis.


<!-- GETTING STARTED -->
## Getting Started

To get a local copy up and running follow these simple steps.

### Installation

1. The easiest way to install the library is to use pip:
   ```sh
   pip install atomicshop
   ```
   
2. If you want to use the latest version, you can download or clone the repo:
   ```sh
   git clone https://github.com/BugSec-Official/atomicshop.git
   ```
    Extract it and install it using pip:
    ```sh
   pip install .
   ```
   If you're on windows you can use the 'Setup.cmd' provided in the repo.



<!-- USAGE EXAMPLES -->
## Usage

To follow. For now, check the files in the library. I tried my best with understandable naming and grouping convention.



<!-- KNOWN REQUIREMENTS -->
## Known Requirements

* pip install SpeechRecognition
  * atomicshop.speech_recognize
* pip install psutil
  * atomicshop.process
  * atomicshop.wrappers.psutilw
* pip install SoundCard
  * atomicshop.sound
* pip install soundfile
  * atomicshop.sound
* pip install numpy
  * atomicshop.wrappers.numpyw
* pip install pyopenssl
  * atomicshop.clones.certauth
* pip install tldextract
  * atomicshop.clones.certauth
* pip install pywintrace
  * atomicshop.etw.etw




<!-- LICENSE -->
## License

Distributed under the MIT License. See `LICENSE.txt` for more information.



<!-- HISTORY -->
## History

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

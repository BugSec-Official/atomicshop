<h1 align="center">Atomic Workshop</h1>



<!-- ABOUT THE PROJECT -->
## About The Project

Atomic Workshop is python's library that was built by Denis Kras under Bugsec's roof.

Use this library at your own risk as it comes with no guarantees at all.
Bugsec or Denis Kras are not responsible for any damage caused to you or any other parties by using this library or suggesting it.

The main purpose of the library is to simplify the process of developing under python.
The library is constantly being improved and supplemented with new features.
"Atomic" is a key to basic functions that a developer needs in his daily tasks: create directory, iterate over files, read/write files, manipulate lists, dicts, etc.

There are many gems hidden in the library:
* Print API: this is the main feature of this library. It allows you to print colored text, with different styles, with / without stdout / stderr, RTL text, logger usage. The API will be integrated in every function of the library in the future, so you can easily use it controlling outputs.
* Windows ETW - Event Tracing: a wrapper for FireEye project's ETW library with much easier API. Sice FireEye didn't update their library for quite a while, maybe another solution will be considered in the future. If you have suggestions, please let me know.
* Windows DNS Event Tracing: Traces DNS requests / responses (Event ID: 3008) on Windows OSes that support Event Tracing. Outputs the real domain (not CDN: AWS, GoogleCloud, Azure, etc) with PID. Process Name and Command Line can be retrieved by option (currently CPU intensive).
* Socket wrapper: can be used to create a server or client and manipulate sockets with relatively easy API. Server tester available.
* MITM Proxy: allows you to create a TCP proxy server (works with SSL) that will intercept requests and responses. You can modify them, log them, etc. ReadMe to follow. Based on SocketWrapper.
* Update checker: helps on checking if pyhon object, a file or any other thing was updated between checks.
* Timer: measures time passed from the point you start it using python API.
* GitHub wrapper: easily download branches and latest releases from GitHub repositories.
* Archiver: extract archives using options.
* ConfigParserWrapper: read / write config files to dict, converting string values to other formats (int, bool, list, list_of_ints, etc).
* And many more: file downloader with status, file csv / json / text reader / writer, simple scheduler with threads, process wrapper, http parser, etc.

Currently, for complete picture you'll have to check the files in the library. I tried my best with understandable naming and grouping convention.
Probably in the future docs generated by SPHINX will follow. Currently most of the functions have docstrings with usage and examples.

Most of the functions presented here are atomic, meaning you can use them almost in any project.
Also, most of the functions were written with optimization in mind.
Meaning, they are fast and easy to use.
Some of them are presented as example of how to do something, to lessen querying to Google, StackOverflow and alike.

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
   
2. If you want to use the latest version, you can clone the repo:
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



<!-- LICENSE -->
## License

Distributed under the MIT License. See `LICENSE.txt` for more information.
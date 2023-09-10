. Download Visual Studio Community 2022, execute the installer.
. On the installer click the [Workloads] tab.
. In "Desktop & Mobile" section, Check
[V] Desktop Development with C++
. On the right pane under "Installation details" select the Windows SDK that you want to compile your DLL to.
. In the bottom righ corner click [Install while downloading].
. Create a folder for all the inclusions and libraries, like:
c:\compile\inc
c:\compile\lib
. Copy all the files from these fodlers to the "inc" folder:
c:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.37.32822\include\
c:\Program Files (x86)\Windows Kits\10\Include\10.0.20348.0\um\
c:\Program Files (x86)\Windows Kits\10\Include\10.0.20348.0\shared\
c:\Program Files (x86)\Windows Kits\10\Include\10.0.20348.0\ucrt\
. Copy all the files from these fodlers to the "lib" folder:
c:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.37.32822\lib\x64\
c:\Program Files (x86)\Windows Kits\10\Lib\10.0.20348.0\um\x64\
c:\Program Files (x86)\Windows Kits\10\Lib\10.0.20348.0\ucrt\x64\

. Run in cmd with admin:
"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.37.32822\bin\Hostx64\x64\cl.exe" /LD /EHsc c:\compile\process_list.cpp /Fo:c:\compile /Fe:c:\compile\process_list.dll /I c:\compile\inc\ /link /LIBPATH:c:\compile\lib\ Advapi32.lib ntdll.lib Psapi.lib

The CL is executed under x64 architecture.
/EHsc: If you have try/except, you need to  activate this.
c:\compile\process_list.cpp: is the place of the cpp file to compile.
/Fo:c:\compile: The place where to save the CFG file.
/Fe:c:\compile\process_list.dll: The path to save the DLL.
/I c:\compile\inc\: Explicit path to all the includes files.
/LIBPATH:c:\compile\lib\: The path to all the lib files.
Advapi32.lib ntdll.lib Psapi.lib: Lib files that are specified explicitly to load.
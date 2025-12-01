REM Install WIndows 10 SDK before running.
REM Execute this cmd in:
REM Start => All Apps => Visual Studio 2022 => x64 Native Tools Command Prompt for VS 2022
REM Run the prompt as admin.
REM "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.39.33519\bin\Hostx64\x64\cl.exe" /LD /EHsc c:\compile\process_list.cpp /Fo:c:\compile /Fe:c:\compile\process_list.dll /I c:\compile\inc\ /link /LIBPATH:c:\compile\lib\ Advapi32.lib ntdll.lib Psapi.lib
cl /LD /EHsc c:\compile\process_list.cpp /Fo:c:\compile /Fe:c:\compile\process_list.dll /I c:\compile\inc\ /link /LIBPATH:c:\compile\lib\ Advapi32.lib ntdll.lib Psapi.lib
pause
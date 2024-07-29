@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"
cd "helpers"
call install_python_as_admin.cmd 3.12

rem Read the contents of the file into a variable
for /f "delims=" %%i in (python_path.txt) do (
    set "dirPath=%%i"
)

rem Adding this so pip will not give an error during execution.
rem Though after adding this you still can't use 'pip' as a command, only full file path.
set PATH=%PATH%;%dirPath%;%dirPath%\Scripts
echo Updated PATH
echo %PATH%

rem Construct the full path to pip
set pipPath=%dirPath%\Scripts\pip.exe

echo Pip path: %pipPath%

rem Execute pip from the specified directory
rem You can't use 'python -m pip' since there are some dependencies that will work only after restart.
"%pipPath%" install --upgrade atomicshop
"%pipPath%" install --upgrade atomicshop

rem Install PyWinTrace
"%pipPath%" install https://github.com/fireeye/pywintrace/releases/download/v0.3.0/pywintrace-0.3.0-py3-none-any.whl

del python_path.txt

endlocal

echo Restarting in 60 seconds.
shutdown -f -r -t 60
pause
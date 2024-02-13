REM cd..
REM echo Trying to uninstall 'productname_server' in case it was installed.
REM pip uninstall -y productname_server
REM pip install -e "%~dp0..."
pip install --upgrade .
REM rmdir /S /Q productname_server.egg-info
REM /d tells the command to operate on directories.
REM /r makes the search recursive, looking into subdirectories.
REM /r option in the for command is followed by a dot (.), which represents the current directory.
REM %i is a variable that holds each directory name found that matches the pattern.
REM *.egg-info* is the search pattern that matches directory names containing .egg-info.
REM rd is the command to remove directories.
REM /s removes the specified directory and all its subdirectories and files.
REM /q runs the rd command in quiet mode, not asking for confirmation.
for /d /r . %%i in (*.egg-info*) do rd /s /q "%%i"
rmdir /S /Q build
pause
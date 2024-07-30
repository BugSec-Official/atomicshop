@echo off
setlocal

rem URL to the raw CMD script file on GitHub
set "URL=https://raw.githubusercontent.com/BugSec-Official/atomicshop/main/setups/scripts/install_PyCharm_as_admin.cmd"

rem Path to save the downloaded script
set "SCRIPT_PATH=%TEMP%\install_PyCharm_as_admin.cmd"

rem Download the script using curl
curl -o "%SCRIPT_PATH%" %URL%

rem Execute the downloaded script
call "%SCRIPT_PATH%"

endlocal
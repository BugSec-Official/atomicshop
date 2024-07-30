@echo off
setlocal

rem URL to the ZIP archive of the repository (main branch in this example)
set "REPO_URL=https://github.com/BugSec-Official/atomicshop/archive/refs/heads/main.zip"

rem Path to save the downloaded ZIP file
set "ZIP_PATH=%TEMP%\atomicshop_main_repo.zip"

rem Path to extract the ZIP file
set "EXTRACT_PATH=%TEMP%\atomicshop_main_repo"

rem Path to extract the specific files
set "EXTRACT_TEMP_PATH=%TEMP%\atomicshop_extract_temp"

rem Download the ZIP file using curl
curl -L -o "%ZIP_PATH%" %REPO_URL%

rem Ensure the temporary extraction path exists
if exist "%EXTRACT_TEMP_PATH%" rd /s /q "%EXTRACT_TEMP_PATH%"
mkdir "%EXTRACT_TEMP_PATH%"

rem Extract the ZIP file using PowerShell
powershell -Command "Expand-Archive -Path '%ZIP_PATH%' -DestinationPath '%EXTRACT_TEMP_PATH%'"

rem Move only the required files/folders to the final extraction path
mkdir "%EXTRACT_PATH%"
xcopy "%EXTRACT_TEMP_PATH%\atomicshop-main\setups\scripts\install_python_and_atomic_as_admin.cmd" "%EXTRACT_PATH%\setups\" /s /i
xcopy "%EXTRACT_TEMP_PATH%\atomicshop-main\setups\scripts\helpers" "%EXTRACT_PATH%\setups\helpers\" /s /i
REM robocopy ""%EXTRACT_TEMP_PATH%\atomicshop-main\setups\scripts" "%EXTRACT_PATH%\setups" install_python_and_atomic_as_admin.cmd
REM robocopy "%EXTRACT_TEMP_PATH%\atomicshop-main\setups\scripts\helper" "%EXTRACT_PATH%\setups\helper" /E

rem Navigate to the extracted setups folder
cd /d "%EXTRACT_PATH%\setups"

rem Execute the install.cmd script
call install_python_and_atomic_as_admin.cmd

rem Clean up temporary files
rd /s /q "%EXTRACT_TEMP_PATH%"

endlocal
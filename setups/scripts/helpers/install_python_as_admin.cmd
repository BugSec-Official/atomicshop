REM Verion 1.0.0
@echo off
setlocal

rem Check if Python version is provided
if "%~1"=="" (
    echo Usage: %0 ^<PythonVersion^>
    echo Example: %0 3.12
    exit /b 1
)

set "PYTHON_VERSION=%~1"
set "PYTHON_MAJOR_MINOR=%PYTHON_VERSION:~0,4%"
set "TARGET_DIR=C:\Python%PYTHON_VERSION:.=%"

REM add installation target dir to environment PATH.
REM set PATH=%PATH%;%TARGET_DIR%;%TARGET_DIR%\Scripts
REM echo Updated PATH
REM echo %PATH%

REM This approach is better than 
REM echo %TARGET_DIR% > python_path.txt
REM Since additional space is not added to the text and no line skip.
(
    echo|set /p="%TARGET_DIR%"
) > python_path.txt

rem Debug: Show variables
echo PYTHON_VERSION: %PYTHON_VERSION%
echo PYTHON_MAJOR_MINOR: %PYTHON_MAJOR_MINOR%
echo TARGET_DIR: %TARGET_DIR%

rem Find the latest patch version
echo Finding the latest patch version for Python %PYTHON_MAJOR_MINOR%...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$url = 'https://www.python.org/ftp/python/';" ^
    "$page = Invoke-WebRequest -Uri $url;" ^
    "$versions = $page.Links | Where-Object { $_.href -match '^\d+\.\d+\.\d+/$' } | ForEach-Object { $_.href.TrimEnd('/') };" ^
    "$latest_version = ($versions | Where-Object { $_ -like '3.12.*' }) | Sort-Object { [version]$_ } -Descending | Select-Object -First 1;" ^
    "Write-Output $latest_version" > latest_version.txt

rem Debug: Show the content of latest_version.txt
type latest_version.txt

set /p LATEST_VERSION=<latest_version.txt
del latest_version.txt

rem Debug: Show the latest version
echo LATEST_VERSION: %LATEST_VERSION%

if "%LATEST_VERSION%"=="" (
    echo Failed to find the latest patch version for Python %PYTHON_MAJOR_MINOR%.
    exit /b 1
)

rem Download the latest Python installer for the determined version
echo Fetching the latest installer for Python %LATEST_VERSION%...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$url = 'https://www.python.org/ftp/python/%LATEST_VERSION%';" ^
    "$page = Invoke-WebRequest -Uri $url;" ^
    "$installer = ($page.Links | Where-Object { $_.href -match 'python-%LATEST_VERSION%.*\.exe$' } | Select-Object -First 1).href;" ^
    "$installer_url = $url + '/' + $installer;" ^
    "Write-Output $installer_url" > installer_url.txt

rem Debug: Show the content of installer_url.txt
type installer_url.txt

set /p INSTALLER_URL=<installer_url.txt
del installer_url.txt

rem Debug: Show the installer URL
echo INSTALLER_URL: %INSTALLER_URL%

if "%INSTALLER_URL%"=="" (
    echo Failed to retrieve the installer URL for Python %LATEST_VERSION%.
    exit /b 1
)

echo Downloading the installer from %INSTALLER_URL%...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri %INSTALLER_URL% -OutFile python_installer.exe"

rem Install Python with specified switches
echo Installing Python %LATEST_VERSION%...
python_installer.exe /passive InstallAllUsers=1 PrependPath=1 TargetDir="%TARGET_DIR%" AssociateFiles=1 InstallLauncherAllUsers=1

rem Clean up
del python_installer.exe

echo Python %LATEST_VERSION% installation completed.
endlocal
exit /b 0

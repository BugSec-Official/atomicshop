REM Version 1.0.0
@echo off
setlocal

rem Check if Python version is provided
if "%~1"=="" (
    echo Usage: %0 ^<PythonVersion^>
    echo Example: %0 3.12
    exit /b 1
)

rem ===== Parse requested version =====
set "PYTHON_VERSION=%~1"
for /f "tokens=1-3 delims=." %%A in ("%PYTHON_VERSION%") do (
    set "PV_MAJOR=%%A"
    set "PV_MINOR=%%B"
    set "PV_PATCH=%%C"
)

set "PYTHON_MAJOR_MINOR=%PV_MAJOR%.%PV_MINOR%"
echo Requested Python version: %PYTHON_MAJOR_MINOR%

rem ===== Decide target architecture (defaults to amd64) =====
set "ARCH=amd64"
if /I "%PROCESSOR_ARCHITECTURE%"=="x86" set "ARCH=x86"
if /I "%PROCESSOR_ARCHITEW6432%"=="x86" set "ARCH=amd64"

echo ARCHITECTURE: %ARCH%


rem ===== Work out LATEST_VERSION =====
if not "%PV_PATCH%"=="" (
    rem An exact patch was provided, e.g. 3.12.10
    set "LATEST_VERSION=%PV_MAJOR%.%PV_MINOR%.%PV_PATCH%"

    echo Provided version: %LATEST_VERSION%
    GOTO Finalize
) else (
    GOTO FindLatestVersion
)

:FindLatestVersion
rem Find the latest patch version
echo Finding the latest patch version for Python %PYTHON_MAJOR_MINOR%...

for /f "usebackq delims=" %%I in (`^
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$url = 'https://www.python.org/ftp/python/';" ^
    "$page = Invoke-WebRequest -Uri $url;" ^
    "$versions = $page.Links | Where-Object { $_.href -match '^\d+\.\d+\.\d+/$' } | ForEach-Object { $_.href.TrimEnd('/') };" ^
    "$latest_version = ($versions | Where-Object { $_ -like '%PYTHON_MAJOR_MINOR%.*' }) | Sort-Object { [version]$_ } -Descending | Select-Object -First 1;" ^
    "Write-Output $latest_version"^
    `) do set "LATEST_VERSION=%%I"

rem Debug: Show the latest version
echo LATEST_VERSION: %LATEST_VERSION%

if "%LATEST_VERSION%"=="" (
    echo Failed to find the latest patch version for Python %PYTHON_MAJOR_MINOR%.
    exit /b 1
)

:Finalize
set "TARGET_DIR=C:\Python%LATEST_VERSION:.=%"
echo TARGET INSTALLATION DIR: %TARGET_DIR%

rem Download the latest Python installer for the determined version
echo Fetching the latest installer for Python %LATEST_VERSION%...

for /f "usebackq delims=" %%I in (`^
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$url = 'https://www.python.org/ftp/python/%LATEST_VERSION%';" ^
    "$page = Invoke-WebRequest -Uri $url;" ^
    "$installer = ($page.Links | Where-Object { $_.href -match 'python-%LATEST_VERSION%.*%ARCH%.*\.exe$' } | Select-Object -First 1).href;" ^
    "$installer_url = $url + '/' + $installer;" ^
    "Write-Output $installer_url"^
    `) do set "INSTALLER_URL=%%I"

rem Debug: Show the installer URL
echo INSTALLER_URL: %INSTALLER_URL%

if "%INSTALLER_URL%"=="%INSTALLER_URL:.exe=%" (
    echo No ".exe" found in INSTALLER_URL.
    echo Try using the installer again by providing the lower exact version, eg. 3.12.10.
    exit /b 1
) else (
    echo ".exe" found in INSTALLER_URL
)

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
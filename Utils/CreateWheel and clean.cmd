@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Project root = parent folder of this script
set "ROOT=%~dp0.."
pushd "%ROOT%" || exit /b 1

echo ============================================================
echo Cleaning __pycache__ under: "%CD%"
echo ============================================================

set /a REMOVED_PYCACHE=0
for /d /r "%CD%" %%G in (__pycache__) do (
    if exist "%%G" (
        echo Removing directory: "%%G"
        rd /s /q "%%G"
        if not exist "%%G" (
            set /a REMOVED_PYCACHE+=1
        ) else (
            echo   WARNING: Could not remove: "%%G"
        )
    )
)

echo.
echo Removed __pycache__ directories: %REMOVED_PYCACHE%
echo.

echo ============================================================
echo Cleaning stray bytecode files (*.pyc, *.pyo) under: "%CD%"
echo ============================================================

set /a REMOVED_PYCS=0
for /r "%CD%" %%F in (*.pyc *.pyo) do (
    if exist "%%F" (
        echo Removing file: "%%F"
        del /f /q "%%F" >nul 2>&1
        if not exist "%%F" (
            set /a REMOVED_PYCS+=1
        ) else (
            echo   WARNING: Could not remove: "%%F"
        )
    )
)

echo.
echo Removed bytecode files: %REMOVED_PYCS%
echo.

echo ============================================================
echo Cleaning build artifacts
echo ============================================================

if exist dist (
    echo Removing directory: "%CD%\dist"
    rmdir /s /q dist
)
if exist build (
    echo Removing directory: "%CD%\build"
    rmdir /s /q build
)

echo ============================================================
echo Building wheel
echo ============================================================
python -m build --wheel .

echo ============================================================
echo Cleaning *.egg-info
echo ============================================================
for /d %%D in ("*.egg-info") do (
    echo Removing directory: "%%~fD"
    rd /s /q "%%~fD"
)

if exist build (
    echo Removing directory: "%CD%\build"
    rmdir /s /q build
)

popd
pause

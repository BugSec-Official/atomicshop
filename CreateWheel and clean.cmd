REM run this file in the same location as 'pyproject.toml'.
del /f "%~dp0*.whl"
REM Install 'build' library: pip install build
python -m build --wheel "%~dp0."
copy "%~dp0dist\*.whl" "%~dp0"
rmdir /S /Q atomicshop.egg-info
rmdir /S /Q build
rmdir /S /Q dist
pause
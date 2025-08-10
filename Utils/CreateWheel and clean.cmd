cd..
REM run this file in the same location as 'pyproject.toml'.
rmdir /S /Q dist
REM Install 'build' library: pip install build
python -m build --wheel .
rmdir /S /Q atomicshop.egg-info
rmdir /S /Q build
pause
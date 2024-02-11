cd..
REM run this file in the same location as 'pyproject.toml'.
rmdir /S /Q dist
REM Install 'build' library: pip install build
REM python -m build --wheel .
python setup.py bdist_wheel
rmdir /S /Q atomicshop.egg-info
rmdir /S /Q build
pause
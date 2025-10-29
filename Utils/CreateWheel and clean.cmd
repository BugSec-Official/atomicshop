cd..
REM run this file in the same location as 'pyproject.toml'.
rmdir /S /Q dist
REM Install 'build' library: pip install build
python -m build --wheel .

REM delete any *.egg-info directory(ies)
for /d %%D in ("*.egg-info") do rd /s /q "%%~fD"

rmdir /S /Q build
pause
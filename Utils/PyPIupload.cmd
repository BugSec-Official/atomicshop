REM run this file in the same location as 'pyproject.toml'.
REM Install 'wheel' library: pip install wheel

REM Basic check.
python -m twine check "%~dp0dist/*"
pause
REM Upload the package.
python -m twine upload "%~dp0dist/*"
pause

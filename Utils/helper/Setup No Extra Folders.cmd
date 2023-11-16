echo Trying to uninstall 'atomicshop' in case it was installed.
pip uninstall -y atomicshop
pip install "%~dp0."
REM python "%~dp0Setup.py" install
rmdir /S /Q atomicshop.egg-info
rmdir /S /Q build
REM pause
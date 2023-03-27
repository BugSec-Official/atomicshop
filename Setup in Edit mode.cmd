echo Trying to uninstall 'atomicshop' in case it was installed.
pip uninstall -y atomicshop
pip install -e "%~dp0."
REM pip install --upgrade -e "%~dp0."
rmdir /S /Q atomicshop.egg-info
rmdir /S /Q build
pause
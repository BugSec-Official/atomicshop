cd..
echo Trying to uninstall 'atomicshop' in case it was installed.
REM pip uninstall -y atomicshop
REM pip install -e "%~dp0..."
pip install --upgrade -e .
rmdir /S /Q atomicshop.egg-info
rmdir /S /Q build
pause
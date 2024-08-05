# Rename this file to __init__.py to make it a package.
# This file will import all the modules inside the directory.

import os
import pkgutil


# Get the directory of the current file (__init__.py) with "os.path.dirname(__file__)".
# Iterate over all the files/modules in the directory
for (_, _module_name, _) in pkgutil.iter_modules([os.path.dirname(__file__)]):
    # Import the module and Update the current namespace with the imported module.
    globals()[_module_name] = __import__(__name__ + '.' + _module_name, fromlist=[_module_name])

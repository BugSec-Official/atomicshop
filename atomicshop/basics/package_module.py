"""
# Add static files to your package / module pyproject.toml:
[tool.setuptools.package-data]
"atomicshop.addons" = ["**"]

# Read relative path of your module inside your package / module script:
from importlib.resources import files
PACKAGE_DLL_PATH = 'addons/process_list/compiled/Win10x64/process_list.dll'
FULL_DLL_PATH = str(files(__package__).joinpath(PACKAGE_DLL_PATH))
"""
engine_name = '_example'
domains = ['example.com']
# This script should be in 'engines' folder.


# === Create template from above settings. ===
# Get current file directory, should be the 'engines' directory.
# noinspection PyPep8
from atomicshop import filesystem
engines_path = filesystem.get_working_directory()
# Create the template.
from atomicshop.mitm.engines.create_module_template import CreateModuleTemplate
CreateModuleTemplate(engine_name, domains, engines_path)

# v1.0.0 - 26.03.2023 15:10
# These are specified with hardcoded paths instead of relative, because 'create_module_template.py' copies the content.
from atomicshop.mitm.engines.__parent.recorder___parent import RecorderParent
from atomicshop.mitm.shared_functions import create_custom_logger
from atomicshop.mitm.message import ClientMessage


# The class that is responsible for Recording Requests / Responses
class RecorderGeneral(RecorderParent):
    logger = create_custom_logger()

    # When initializing main classes through "super" you need to pass parameters to init
    def __init__(self, class_client_message: ClientMessage, record_path):
        super().__init__(class_client_message, record_path)

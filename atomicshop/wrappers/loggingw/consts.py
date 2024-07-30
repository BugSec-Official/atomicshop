DEFAULT_ROTATING_SUFFIXES_FROM_WHEN: dict = {
    'midnight': '%Y-%m-%d',
    'S': '%Y-%m-%d_%H-%M-%S',
    'M': '%Y-%m-%d_%H-%M',
    'H': '%Y-%m-%d_%H',
    'D': '%Y-%m-%d',
    'W0': '%Y-%m-%d',
    'W1': '%Y-%m-%d',
    'W2': '%Y-%m-%d',
    'W3': '%Y-%m-%d',
    'W4': '%Y-%m-%d',
    'W5': '%Y-%m-%d',
    'W6': '%Y-%m-%d'
}


DEFAULT_STREAM_FORMATTER: str = "%(levelname)s | %(threadName)s | %(name)s | %(message)s"
DEFAULT_MESSAGE_FORMATTER: str = "%(message)s"

FORMAT_ELEMENT_TO_HEADER: dict = {
    'asctime': 'Event Time [Y-M-D H:M:S]',
    'created': 'Created',
    'filename': "ModuleFileName            ",
    'funcName': 'Function',
    'levelname': 'Log Level',
    'levelno': 'Level Number',
    'lineno': 'Line ',
    'module': 'Module',
    'msecs': '[MS.mS]',
    'message': 'Message',
    'name': 'Logger Name                     ',
    'pathname': 'Path',
    'process': 'Process',
    'processName': 'Process Name',
    'relativeCreated': 'Relative Created',
    'thread': 'Thread',
    'threadName': 'Thread Name'
}

DEFAULT_FORMATTER_TXT_FILE: str = \
    "{asctime} | " \
    "{levelname:<" + f"{len(FORMAT_ELEMENT_TO_HEADER['levelname'])}" + "s} | " \
    "{name:<" + f"{len(FORMAT_ELEMENT_TO_HEADER['name'])}" + "s} | " \
    "{filename:<" + f"{len(FORMAT_ELEMENT_TO_HEADER['filename'])}" + "s} : " \
    "{lineno:<" + f"{len(FORMAT_ELEMENT_TO_HEADER['lineno'])}" + "d} | " \
    "{threadName} | {message}"

DEFAULT_FORMATTER_CSV_FILE: str = \
    '\"{asctime}\",{levelname},{name},{filename},{lineno},{threadName},\"{message}\"'

from .import rest_firmware, rest_statistics


def endpoint_router(config: dict):
    """
    Route the endpoint.
    :param config: dict, configuration dictionary.
    :return:
    """

    if config['method'] == 'upload_firmware':
        rest_firmware.upload_files(config['firmwares_path'], config['data'])
    elif config['method'] == 'stats':
        rest_statistics.get_statistics()

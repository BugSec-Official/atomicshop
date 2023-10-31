from .import firmware, statistics, binary_search


def endpoint_router(config: dict):
    """
    Route the endpoint.
    :param config: dict, configuration dictionary.
    :return:
    """

    if config['method'] == 'upload_firmware':
        firmware.upload_files(config['firmwares_path'], config['data'])
    elif config['method'] == 'firmware_csv':
        firmware.save_firmware_uids_as_csv(
            directory_path=config['output_path'], config_data=config['data'], get_analysis_data=True)
    elif config['method'] == 'get_statistics':
        statistics.get_statistics()
    elif config['method'] == 'binary_search':
        binary_search.search_string(config['data']['vendor'])

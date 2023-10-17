from atomicshop import filesystem
from atomicshop.wrappers.factw import upload_firmware


def upload_files(directory_path: str, params: dict):
    """
    Upload Siemens firmware binary files from specified directory to the server.
    :param directory_path: string, path to directory with firmware binary files.
    :param params: dict of REST params.
    :return:
    """

    # Get all the UPD files.
    file_paths_list = filesystem.get_file_paths_and_relative_directories(directory_path, recursive=False)

    firmwares: list = list()
    for file_path in file_paths_list:
        firmware_info: dict = dict()
        firmware_info['file_path'] = file_path['path']
        firmware_info['file_name'] = filesystem.get_file_name_with_extension(file_path['path'])
        firmwares.append(firmware_info)

    use_all_analysis_systems: bool = False
    for firmware in firmwares:
        params['file_name'] = firmware['file_name']

        if params['requested_analysis_systems'] == 'all' and not use_all_analysis_systems:
            use_all_analysis_systems = True

        upload_firmware.upload_firmware(
            firmware['file_path'], params, use_all_analysis_systems=use_all_analysis_systems)

    return None

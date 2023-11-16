from atomicshop.process import execute_with_live_output


def execute_pbtk(pbtk_path: str, file_path: str, target_directory: str) -> None:
    """
    The function receives file path and target filesystem directory to extract the files.

    :param pbtk_path: full path to pbtk file.
    :param file_path: full path to binary file.
    :param target_directory: The directory on the filesystem to extract files.
    """

    cmd: str = f'python "{pbtk_path}" "{file_path}" "{target_directory}"'
    print(f'Scanning: {file_path}')

    output_list = execute_with_live_output(cmd=cmd)

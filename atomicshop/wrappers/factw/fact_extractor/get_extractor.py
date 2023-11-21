from .... import filesystem, web


def get_extractor_script(target_directory: str = None):
    """
    Download the FACT extractor script that interacts with the docker.
    Download the file to the main.py directory.
    :return:

    Main.py usage:
        from atomicshop.wrappers.factw.fact_extractor import get_extractor


        def main():
            get_extractor.get_extractor_script()


        if __name__ == '__main__':
            main()
    """

    if target_directory is None:
        target_directory: str = filesystem.get_working_directory()
    file_url: str = 'https://raw.githubusercontent.com/fkie-cad/fact_extractor/master/extract.py'
    web.download(file_url=file_url, target_directory=target_directory)

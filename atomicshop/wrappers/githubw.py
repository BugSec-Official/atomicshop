import requests
import fnmatch

from ..web import download_and_extract_file
from ..print_api import print_api
from ..urls import url_parser


class GitHubWrapper:
    # You also can use '.tar.gz' as extension.
    def __init__(
            self, user_name: str = str(), repo_name: str = str(), repo_url: str = str(),
            branch: str = 'master', branch_file_extension: str = '.zip'):
        self.user_name: str = user_name
        self.repo_name = repo_name
        self.repo_url: str = repo_url
        self.branch: str = branch
        self.branch_file_extension: str = branch_file_extension

        # Default variables.
        self.archive_directory: str = 'archive'
        self.branch_file_name: str = f'{self.branch}{self.branch_file_extension}'
        self.domain: str = 'github.com'

        # Initialize variables.
        self.branch_download_link: str = str()
        self.branch_downloaded_folder_name: str = str()
        self.latest_release_json_url: str = str()

    def build_links_from_user_and_repo(self, **kwargs):
        if not self.user_name or not self.repo_name:
            message = "'user_name' or 'repo_name' is empty."
            print_api(message, color="red", error_type=True, **kwargs)

        self.repo_url = f'https://{self.domain}/{self.user_name}/{self.repo_name}'
        self.branch_download_link = f'{self.repo_url}/{self.archive_directory}/{self.branch_file_name}'
        self.branch_downloaded_folder_name = f'{self.repo_name}-{self.branch}'
        self.latest_release_json_url: str = \
            f'https://api.{self.domain}/repos/{self.user_name}/{self.repo_name}/releases/latest'

    def build_links_from_repo_url(self, **kwargs):
        if not self.repo_url:
            message = "'repo_url' is empty."
            print_api(message, color="red", error_type=True, **kwargs)

        repo_url_parsed = url_parser(self.repo_url)
        self.check_github_domain(repo_url_parsed['netloc'])
        self.user_name = repo_url_parsed['directories'][0]
        self.repo_name = repo_url_parsed['directories'][1]

        self.build_links_from_user_and_repo()

    def check_github_domain(self, domain):
        if self.domain not in domain:
            print_api(
                f'This is not [{self.domain}] domain.', color="red", error_type=True)

    def download_and_extract_branch(
            self,
            target_directory: str,
            archive_remove_first_directory: bool = False,
            **kwargs
    ):
        """
        This function will download the branch file from GitHub, extract the file and remove the file, leaving
        only the extracted folder.

        :param target_directory:
        :param archive_remove_first_directory: boolean, sets if archive extract function will extract the archive
            without first directory in the archive. Check reference in the 'archiver.extract_archive_with_zipfile'
            function.
        :return:
        """

        # Download the repo to current working directory, extract and remove the archive.
        download_and_extract_file(
            file_url=self.branch_download_link,
            target_directory=target_directory,
            archive_remove_first_directory=archive_remove_first_directory,
            **kwargs)

    def download_and_extract_latest_release(
            self, target_directory: str, string_pattern: str,
            archive_remove_first_directory: bool = False, **kwargs):
        # Download latest release url.
        response = requests.get(self.latest_release_json_url)
        # Response from the latest releases page is json. Convert response to json from downloaded format and get
        # 'assets' key.
        github_latest_releases_list = response.json()['assets']

        # Get only download urls of the latest releases.
        download_urls: list = list()
        for single_dict in github_latest_releases_list:
            download_urls.append(single_dict['browser_download_url'])

        # Find urls against 'string_pattern'.
        found_urls = fnmatch.filter(download_urls, string_pattern)

        # If more than 1 url answer the criteria, we can't download it. The user must be more specific in his input
        # strings.
        if len(found_urls) > 1:
            message = f'More than 1 result found in JSON response, try changing search string or extension.\n' \
                      f'{found_urls}'
            print_api(message, color="red", error_type=True, **kwargs)

        download_and_extract_file(
            file_url=found_urls[0],
            target_directory=target_directory,
            archive_remove_first_directory=archive_remove_first_directory,
            **kwargs)

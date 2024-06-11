import requests
import fnmatch

from .. import web, urls
from ..print_api import print_api
from ..basics import strings


class GitHubWrapper:
    # You also can use '.tar.gz' as extension.
    def __init__(
            self,
            user_name: str = None,
            repo_name: str = None,
            repo_url: str = None,
            branch: str = 'master',
            branch_file_extension: str = '.zip'
    ):
        """
        This class is a wrapper for GitHub repositories. It can download the branch file from the repository and extract
        it to the target directory and more.

        :param user_name: str, the user-name of the repository.
             https://github.com/{user_name}/{repo_name}
        :param repo_name: str, the repository name.
        :param repo_url: str, the repository url.
            You can provide the full url to the repository directly and then extract the user_name and repo_name from it
            with the 'build_links_from_repo_url' function.
        :param branch: str, the branch name. The default is 'master'.
        :param branch_file_extension: str, the branch file extension. The default is '.zip'.

        ================================================================================================================
        Usage to download the 'master' branch file:
            git_wrapper = GitHubWrapper(user_name='user_name', repo_name='repo_name')
            git_wrapper.download_and_extract_branch(target_directory='target_directory')

        Usage to download the 'main' branch file:
            git_wrapper = GitHubWrapper(user_name='user_name', repo_name='repo_name', branch='main')
            git_wrapper.download_and_extract_branch(target_directory='target_directory')

        You can provide the user_name and repo_name after the initialization of the class:
            git_wrapper = GitHubWrapper()
            git_wrapper.user_name = 'user_name'
            git_wrapper.repo_name = 'repo_name'
            git_wrapper.build_links_from_user_and_repo()
            git_wrapper.download_and_extract_branch(target_directory='target_directory')
        ================================================================================================================
        Usage to download the 'master' branch file from the repository url:
            git_wrapper = GitHubWrapper(repo_url='http://github.com/user_name/repo_name')
            git_wrapper.download_and_extract_branch(target_directory='target_directory')

        Usage to download the 'main' branch file from the repository url:
            git_wrapper = GitHubWrapper(repo_url='http://github.com/user_name/repo_name', branch='main')
            git_wrapper.download_and_extract_branch(target_directory='target_directory')

        You can provide the repo_url after the initialization of the class:
            git_wrapper = GitHubWrapper()
            git_wrapper.repo_url = 'http://github.com/user_name/repo_name'
            git_wrapper.build_links_from_repo_url()
            git_wrapper.download_and_extract_branch(target_directory='target_directory')
        ================================================================================================================
        Usage to download the latest release where the file name is 'test_file.zip':
            git_wrapper = GitHubWrapper(user_name='user_name', repo_name='repo_name')
            git_wrapper.download_and_extract_latest_release(
                target_directory='target_directory', string_pattern='test_*.zip')
        ================================================================================================================
        Usage to get the latest release json:
            git_wrapper = GitHubWrapper(user_name='user_name', repo_name='repo_name')
            git_wrapper.get_the_latest_release_json()
        ================================================================================================================
        Usage to get the latest release version:
            git_wrapper = GitHubWrapper(user_name='user_name', repo_name='repo_name')
            git_wrapper.get_the_latest_release_version_number()
        """

        self.user_name: str = user_name
        self.repo_name: str = repo_name
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

        if self.user_name and self.repo_name and not self.repo_url:
            self.build_links_from_user_and_repo()

        if self.repo_url and not self.user_name and not self.repo_name:
            self.build_links_from_repo_url()

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

        repo_url_parsed = urls.url_parser(self.repo_url)
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
            without first directory in the archive. Check reference in the
            'archiver.zip.extract_archive_with_zipfile' function.
        :return:
        """

        # Download the repo to current working directory, extract and remove the archive.
        web.download_and_extract_file(
            file_url=self.branch_download_link,
            target_directory=target_directory,
            archive_remove_first_directory=archive_remove_first_directory,
            **kwargs)

    def get_latest_release_url(
            self,
            string_pattern: str,
            exclude_string: str = None,
            **kwargs):
        """
        This function will return the latest release url.
        :param string_pattern: str, the string pattern to search in the latest release. Wildcards can be used.
        :param exclude_string: str, the string to exclude from the search. No wildcards can be used.
        :param kwargs: dict, the print arguments for the 'print_api' function.
        :return: str, the latest release url.
        """

        # Get the 'assets' key of the latest release json.
        github_latest_releases_list = self.get_the_latest_release_json()['assets']

        # Get only download urls of the latest releases.
        download_urls: list = list()
        for single_dict in github_latest_releases_list:
            download_urls.append(single_dict['browser_download_url'])

        # Exclude urls against 'exclude_string'.
        if exclude_string:
            for download_url in download_urls:
                if exclude_string in download_url:
                    download_urls.remove(download_url)

        # Find urls against 'string_pattern'.
        found_urls = fnmatch.filter(download_urls, string_pattern)

        # If more than 1 url answer the criteria, we can't download it. The user must be more specific in his input
        # strings.
        if len(found_urls) > 1:
            message = f'More than 1 result found in JSON response, try changing search string or extension.\n' \
                      f'{found_urls}'
            print_api(message, color="red", error_type=True, **kwargs)

        return found_urls[0]

    def download_latest_release(
            self,
            target_directory: str,
            string_pattern: str,
            exclude_string: str = None,
            **kwargs):
        """
        This function will download the latest release from the GitHub repository.
        :param target_directory: str, the target directory to download the file.
        :param string_pattern: str, the string pattern to search in the latest release. Wildcards can be used.
        :param exclude_string: str, the string to exclude from the search. No wildcards can be used.
            The 'excluded_string' will be filtered before the 'string_pattern' entries.
        :param kwargs: dict, the print arguments for the 'print_api' function.
        :return:
        """

        # Get the latest release url.
        found_url = self.get_latest_release_url(string_pattern=string_pattern, exclude_string=exclude_string, **kwargs)

        downloaded_file_path = web.download(file_url=found_url, target_directory=target_directory, **kwargs)
        return downloaded_file_path

    def download_and_extract_latest_release(
            self,
            target_directory: str,
            string_pattern: str,
            exclude_string: str = None,
            archive_remove_first_directory: bool = False,
            **kwargs):
        """
        This function will download the latest release from the GitHub repository, extract the file and remove the file,
        leaving only the extracted folder.
        :param target_directory: str, the target directory to download and extract the file.
        :param string_pattern: str, the string pattern to search in the latest release. Wildcards can be used.
        :param exclude_string: str, the string to exclude from the search. No wildcards can be used.
        :param archive_remove_first_directory: bool, sets if archive extract function will extract the archive
            without first directory in the archive. Check reference in the
            'archiver.zip.extract_archive_with_zipfile' function.
        :param kwargs: dict, the print arguments for the 'print_api' function.
        :return:
        """

        # Get the latest release url.
        found_url = self.get_latest_release_url(string_pattern=string_pattern, exclude_string=exclude_string, **kwargs)

        web.download_and_extract_file(
            file_url=found_url,
            target_directory=target_directory,
            archive_remove_first_directory=archive_remove_first_directory,
            **kwargs)

    def get_the_latest_release_json(self):
        """
        This function will get the latest releases json.
        :return:
        """
        response = requests.get(self.latest_release_json_url)
        return response.json()

    def get_the_latest_release_version_number(self):
        """
        This function will get the latest release version number.
        :return:
        """
        return self.get_the_latest_release_json()['tag_name']

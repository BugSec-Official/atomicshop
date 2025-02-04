import requests
import fnmatch

from .. import web, urls
from ..print_api import print_api


class MoreThanOneReleaseFoundError(Exception):
    pass

class NoReleaseFoundError(Exception):
    pass


class GitHubWrapper:
    def __init__(
            self,
            user_name: str = None,
            repo_name: str = None,
            repo_url: str = None,
            branch: str = 'master',
            path: str = None,
            pat: str = None,
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
        :param path: str, the path to the file/folder inside the repo that we'll do certain actions on.
             Actions example: get_latest_commit_comment, download_path_from_branch.
        :param pat: str, the personal access token to the repo.
        :param branch_file_extension: str, the branch file extension. The default is '.zip'.
            You also can use '.tar.gz' as extension.

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
        self.path: str = path
        self.pat: str = pat
        self.branch_file_extension: str = branch_file_extension

        # Default variables.
        self.archive_directory: str = 'archive'
        self.branch_file_name: str = f'{self.branch}{self.branch_file_extension}'
        self.domain: str = 'github.com'

        # Initialize variables.
        self.branch_download_link: str = str()
        self.branch_downloaded_folder_name: str = str()
        self.api_url: str = str()
        self.latest_release_json_url: str = str()
        self.commits_url: str = str()
        self.contents_url: str = str()

        if self.user_name and self.repo_name and not self.repo_url:
            self.build_links_from_user_and_repo()

        if self.repo_url and not self.user_name and not self.repo_name:
            self.build_links_from_repo_url()

    def _get_headers(self) -> dict:
        """
        Returns headers for the GitHub API requests. If a personal access token (PAT) is provided, it adds the
        'Authorization' header.
        """
        headers = {}
        if self.pat:
            headers['Authorization'] = f'token {self.pat}'
        return headers

    def build_links_from_user_and_repo(self, **kwargs):
        if not self.user_name or not self.repo_name:
            raise ValueError("'user_name' or 'repo_name' is empty.")

        self.repo_url = f'https://{self.domain}/{self.user_name}/{self.repo_name}'
        self.branch_download_link = f'{self.repo_url}/{self.archive_directory}/{self.branch_file_name}'
        self.branch_downloaded_folder_name = f'{self.repo_name}-{self.branch}'

        self.api_url = f'https://api.{self.domain}/repos/{self.user_name}/{self.repo_name}'

        self.latest_release_json_url: str = f'{self.api_url}/releases/latest'
        self.commits_url: str = f'{self.api_url}/commits'
        self.contents_url: str = f'{self.api_url}/contents'

    def build_links_from_repo_url(self, **kwargs):
        if not self.repo_url:
            raise ValueError("'repo_url' is empty.")

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
            download_each_file: bool = False,
            **kwargs
    ):
        """
        This function will download the branch file from GitHub, extract the file and remove the file, leaving
        only the extracted folder.
        If the 'path' was specified during the initialization of the class, only the path will be downloaded.

        :param target_directory: str, the target directory to download the branch/path.
        :param archive_remove_first_directory: boolean, available only if 'path' was not specified during the initialization
            Sets if archive extract function will extract the archive
            without first directory in the archive. Check reference in the
            'archiver.zip.extract_archive_with_zipfile' function.
        :param download_each_file: bool, available only if 'path' was specified during the initialization of the class.
            Sets if each file will be downloaded separately.

            True: Meaning the directory '/home/user/Downloads/files/' will be created and each file will be downloaded
                ('file1.txt', 'file2.txt', 'file3.txt') separately to this directory.
            False: The branch file will be downloaded to temp directory then the provided path
                will be extracted from there, then the downloaded branch directory will be removed.
        :return:
        """

        headers: dict = self._get_headers()

        if not download_each_file:
            # Download the repo to current working directory, extract and remove the archive.
            web.download_and_extract_file(
                file_url=self.branch_download_link,
                target_directory=target_directory,
                archive_remove_first_directory=archive_remove_first_directory,
                headers=headers,
                **kwargs)
        else:
            # Build the URL for the contents API
            contents_url = f"{self.contents_url}/{self.path}"
            params = {'ref': self.branch}

            response = requests.get(contents_url, headers=headers, params=params)
            response.raise_for_status()

            items = response.json()

            # Ensure the target directory exists.
            os.makedirs(target_directory, exist_ok=True)

            for item in items:
                item_path = os.path.join(target_directory, item['name'])
                if item['type'] == 'file':
                    # Download the file using the provided download URL.
                    file_url = item['download_url']
                    # You can reuse your download function here, passing the headers.
                    download(
                        file_url=file_url,
                        target_directory=target_directory,
                        file_name=item['name'],
                        headers=headers
                    )
                elif item['type'] == 'dir':
                    # Recursively download subdirectories.
                    self.download_folder_contents(
                        folder_path=os.path.join(folder_path, item['name']),
                        target_directory=item_path
                    )

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
        found_urls: list = fnmatch.filter(download_urls, string_pattern)

        # If more than 1 url answer the criteria, we can't download it. The user must be more specific in his input
        # strings.
        if len(found_urls) > 1:
            message = f'More than 1 result found in JSON response, try changing search string or extension.\n' \
                      f'{found_urls}'
            raise MoreThanOneReleaseFoundError(message)
        elif len(found_urls) == 0:
            message = f'No result found in JSON response, try changing search string or extension.'
            raise NoReleaseFoundError(message)
        else:
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

        headers: dict = self._get_headers()

        # Get the latest release url.
        found_url = self.get_latest_release_url(string_pattern=string_pattern, exclude_string=exclude_string, **kwargs)

        downloaded_file_path = web.download(
            file_url=found_url, target_directory=target_directory, headers=headers, **kwargs)
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

        headers: dict = self._get_headers()

        # Get the latest release url.
        found_url = self.get_latest_release_url(string_pattern=string_pattern, exclude_string=exclude_string, **kwargs)

        web.download_and_extract_file(
            file_url=found_url,
            target_directory=target_directory,
            archive_remove_first_directory=archive_remove_first_directory,
            headers=headers,
            **kwargs)

    def get_the_latest_release_json(self):
        """
        This function will get the latest releases json.
        :return:
        """

        headers: dict = self._get_headers()

        response = requests.get(self.latest_release_json_url, headers=headers)
        return response.json()

    def get_the_latest_release_version_number(self):
        """
        This function will get the latest release version number.
        :return:
        """
        return self.get_the_latest_release_json()['tag_name']

    def get_latest_commit_comment(self):
        """
        This function retrieves the commit message (comment) of the latest commit on the specified branch.
        It uses the GitHub API endpoint for commits.

        :return: str, the commit message of the latest commit.
        """

        headers: dict = self._get_headers()

        # Use query parameters to filter commits by branch (sha) and limit results to 1
        params: dict = {
            'sha': self.branch,
            'per_page': 1
        }

        if self.path:
            params['path'] = self.path

        response = requests.get(self.commits_url, headers=headers, params=params)
        response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code.

        commits = response.json()
        if not commits:
            return None

        commit_message = commits[0].get("commit", {}).get("message", "")
        return commit_message


def parse_github_args():
    import argparse

    parser = argparse.ArgumentParser(description='GitHub Wrapper')
    parser.add_argument(
        '-u', '--repo_url', type=str, required=True,
        help='The repository url. Example: https://github.com/{user_name}/{repo_name}')
    parser.add_argument(
        '-b', '--branch', type=str, required=True,
        help='The branch name. The specific branch from the repo you want to operate on.')
    parser.add_argument(
        '-p', '--path', type=str, default=None,
        help="The path to the file/folder inside the repo that we'll do certain actions on.\n"
             "Available actions: get_latest_commit_comment, download_path_from_branch.")
    parser.add_argument(
        '-t', '--target_directory', type=str, default=None,
        help='The target directory to download the file/folder.'
    )
    parser.add_argument(
        '--pat', type=str, default=None,
        help='The personal access token to the repo.')
    parser.add_argument(
        '-glcc', '--get_latest_commit_comment', action='store_true', default=False,
        help='Sets if the latest commit comment will be printed.')
    parser.add_argument(
        '-db', '--download_branch', action='store_true', default=False,
        help='Sets if the branch will be downloaded. In conjunction with path, only the path will be downloaded.')

    return parser.parse_args()


def github_wrapper_main(
        repo_url: str,
        branch: str,
        path: str = None,
        target_directory: str = None,
        pat: str = None,
        get_latest_commit_comment: bool = False,
        download_branch: bool = False
):
    """
    This function is the main function for the GitHubWrapper class.
    :param repo_url: str, the repository url.
        Example: https://github.com/{user_name}/{repo_name}
    :param branch: str, the branch name. The specific branch from the repo you want to operate on.
    :param path: str, the path to the file/folder for which the commit message should be retrieved.
    :param target_directory: str, the target directory to download the file/folder.
    :param pat: str, the personal access token to the repo.
    :param get_latest_commit_comment: bool, sets if the latest commit comment will be printed.
    :param download_branch: bool, sets if the branch will be downloaded. In conjunction with path, only the path will be
        downloaded.
    :return:
    """

    git_wrapper = GitHubWrapper(repo_url=repo_url, branch=branch, path=path, pat=pat)

    if get_latest_commit_comment:
        commit_comment = git_wrapper.get_latest_commit_comment()
        print_api(commit_comment)
        return 0

    if download_branch:
        git_wrapper.download_and_extract_branch(
            target_directory=target_directory, download_each_file=True, download_branch_and_extract=False,
            archive_remove_first_directory=True)

        return 0


def github_wrapper_main_with_args():
    args = parse_github_args()

    return github_wrapper_main(
        repo_url=args.repo_url,
        branch=args.branch,
        path=args.path,
        target_directory=args.target_directory,
        pat=args.pat,
        get_latest_commit_comment=args.get_latest_commit_comment
    )
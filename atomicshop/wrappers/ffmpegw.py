# v1.0.3 - 31.03.2023 17:10
import fnmatch
import os
import shlex

from ..print_api import print_api
from ..tempfiles import TempFile
from ..github_wrapper import GitHubWrapper
from ..process import execute_with_live_output
from ..filesystem import create_folder


class FFmpegWrapper:
    def __init__(self, working_directory: str = str(), ffmpeg_exe_path: str = str()):
        self.working_directory: str = working_directory
        self.ffmpeg_exe_path: str = ffmpeg_exe_path
        self.relative_path: str = 'bin'
        self.ffmpeg_exe_name: str = 'ffmpeg.exe'

        # Variables to download the latest release from GitHub in case execution fails.
        self.git_user: str = 'GyanD'
        self.git_repo: str = 'codexffmpeg'
        self.git_latest_release_pattern: str = '*full_build.zip'

        # ffmpeg Release directory name.
        self.ffmpeg_release_directory_name: str = \
            f"ffmpeg_{self.git_latest_release_pattern.replace('*', '').split('.')[0]}"
        self.ffmpeg_release_directory_path: str = str()

        # Execute functions.
        self.build_ffmpeg_exe_and_directory_path()

    def build_ffmpeg_exe_and_directory_path(self):
        # If working directory was specified, but not the full path to exe.
        if self.working_directory and not self.ffmpeg_exe_path:
            self.ffmpeg_release_directory_path = self.working_directory + os.sep + self.ffmpeg_release_directory_name
            self.ffmpeg_exe_path = \
                self.ffmpeg_release_directory_path + os.sep + self.relative_path + os.sep + self.ffmpeg_exe_name
        # If no working directory and no path to exe was specified.
        elif not self.working_directory and not self.ffmpeg_exe_path:
            # Use just 'ffmpeg.exe' as path to exe. Maybe it is already installed and is in environment PATH var.
            self.ffmpeg_exe_path = self.ffmpeg_exe_name

    def change_to_temp_directory(self):
        temp_file = TempFile()
        self.working_directory = temp_file.directory
        self.ffmpeg_exe_path = str()
        self.build_ffmpeg_exe_and_directory_path()

    def download_ffmpeg_and_extract(self):
        github_wrapper = GitHubWrapper(user_name=self.git_user, repo_name=self.git_repo)
        github_wrapper.build_links_from_user_and_repo()
        github_wrapper.download_and_extract_latest_release(
            target_directory=self.ffmpeg_release_directory_path, string_pattern=self.git_latest_release_pattern,
            archive_remove_first_directory=True)

    def execute_ffmpeg(self, cmd_list: list):
        continue_loop: bool = True
        while continue_loop:
            # If first entry contains 'ffmpeg.exe' and it is not 'self.ffmpeg_exe_path' already.
            if self.ffmpeg_exe_name in cmd_list[0] and cmd_list[0] != self.ffmpeg_exe_path:
                # We'll change it to the updated one.
                cmd_list[0] = self.ffmpeg_exe_path
            # If first entry doesn't contain 'ffmpeg.exe'.
            elif self.ffmpeg_exe_name not in cmd_list[0]:
                # We'll insert the current path into first entry.
                cmd_list.insert(0, self.ffmpeg_exe_path)

            output_strings: list = [
                'Input',
                'Output',
                'video:'
            ]

            try:
                print(f'FFmpeg processing: {shlex.join(cmd_list)}')
                result_lines = execute_with_live_output(
                    cmd=cmd_list, output_strings=output_strings, raise_exception=True, exit_on_error=False)
            # If 'ffmpeg.exe' is non-existent.
            except FileNotFoundError:
                # Check if full path to 'ffmpeg.exe' is just 'ffmpeg.exe'.
                if self.ffmpeg_exe_path == self.ffmpeg_exe_name:
                    print_api('Will try temp folder...', raise_exception=False)
                    # Change to temp folder and try executing again.
                    self.change_to_temp_directory()
                    continue

                print_api('Trying to download...', raise_exception=False)
                create_folder(self.ffmpeg_release_directory_path)
                self.download_ffmpeg_and_extract()
                continue

            # === At this point python exceptions are finished. ==========================
            # If 'Invalid argument' was returned by 'ffmpeg' in the last line.
            if 'Invalid argument' in result_lines[-1]:
                print_api(result_lines[-1], message_type_error=True, color="red", exit_on_error=True)

            # === Successful execution section ==========================================
            string_pattern = 'video:*audio:*subtitle*'
            # if 'video:' in result_lines[-1] and 'audio:' in result_lines[-1] and 'subtitle:' in result_lines[-1]:
            if fnmatch.fnmatch(result_lines[-1], string_pattern):
                print_api(f'FFmpeg finished successfully.', color="green")

            # Since exceptions are finished, we can stop the while loop.
            continue_loop = False

    def convert_file(self, source_file_path: str, dest_file_path: str, overwrite: bool = False) -> None:
        """
        The function converts source file to destination file. The source format is defined by the file extension
        as well as destination file format defined by the destination file extension.

        Example convert MP3 file to WAV:
            convert_file(source_file_path=some_music.mp3, dest_file_path=converted_file.wav)

        :param source_file_path: string, full file path to source file.
        :param dest_file_path: string, full file path to destination file.
        :param overwrite: boolean, set if destination file should be overwritten if it exists.
        :return: None.
        """

        cmd_list = ['-i', source_file_path, dest_file_path]

        if overwrite:
            cmd_list.append('-y')

        self.execute_ffmpeg(cmd_list)

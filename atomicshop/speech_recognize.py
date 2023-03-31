# v1.0.0 - 07.03.2023 23:40
from atomicshopext.ffmpeg_wrapper import FFmpegWrapper
from atomicshop.tempfile_operations import TempFile
from atomicshop.web import download_with_urllib


def get_text_from_wav(wav_file_path: str) -> str:
    """
    The function recognizes speech in source WAV file and returns recognized text.

    :param wav_file_path: string, full file path to WAV file.
    :return: string, recognized text from WAV file.
    """

    # Lazy import.
    from speech_recognition import Recognizer, AudioFile


    # Initialize speech recognizer classes.
    speech_recognizer = Recognizer()
    # Import wav file.
    speech_recognizer_recaptcha_audio = AudioFile(wav_file_path)
    # Process the file.
    with speech_recognizer_recaptcha_audio as source:
        audio = speech_recognizer.record(source)
    # Convert to text.
    # When using 'recognize_google' it outputs debugging JSON, there's an option 'show_all=False',
    # which is set by default, could be bug in current version 3.9.0. There are some changes in GitHub for it
    # but not in PyPi, will wait.
    text = speech_recognizer.recognize_google(audio)

    return text


def convert_mp3_and_get_text(mp3_file_path: str, wav_file_path: str) -> str:
    """
    The function will convert source MP3 file to destination WAV file and get text from the converted WAV file.

    :param mp3_file_path: string, full path to source MP3 file.
    :param wav_file_path: string, full path to destination WAV file that MP# will be converted to.
    :return: string, recognized text from WAV file.
    """

    # Convert the file from mp3 to wav, since speech_recognition module works with wav files.
    ffmpeg_wrapper = FFmpegWrapper()
    ffmpeg_wrapper.convert_file(mp3_file_path, wav_file_path, overwrite=True)
    # pydub.AudioSegment.from_mp3(temp_file_mp3.file_path).export(temp_file_wav.file_path, format="wav")

    # Recognize the speech in wav file and return text.
    return get_text_from_wav(wav_file_path)


def download_mp3_convert_and_get_text(audio_file_url: str):
    # Initialize temp file class.
    temp_file_mp3 = TempFile()
    temp_file_wav = TempFile()
    # Download the file.
    temp_file_mp3.file_path = download_with_urllib(audio_file_url, temp_file_mp3.directory)
    # Add the file path to wav temp file including extension '.wav'.
    temp_file_wav.file_path = temp_file_mp3.file_path + ".wav"

    # Convert the file from mp3 to wav, since speech_recognition module works with wav files and get text.
    text = convert_mp3_and_get_text(temp_file_mp3.file_path, temp_file_wav.file_path)

    # Remove temp files.
    temp_file_mp3.remove()
    temp_file_wav.remove()

    return text

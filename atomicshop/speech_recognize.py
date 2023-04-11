from .wrappers.ffmpegw import FFmpegWrapper
from .tempfiles import TempFile
from .web import download
from .basics import strings


STRINGS_TO_NUMBERS: dict = {
    'zero': '0',
    'one': '1',
    'two': '2',
    'three': '3',
    'four': '4',
    'five': '5',
    'six': '6',
    'seven': '7',
    'eight': '8',
    'nine': '9',
}


STRINGS_MISTAKES_TO_NUMBERS: dict = {
    'free': '3',
    'for': '4',
    'hate': '8',
    'sex': '6',
    'sexy': '6'
}


STRINGS_MISTAKES_TO_CHARACTERS: dict = {
    'and': 'n',
    'ass': 's',
    'in': 'n',
    'see': 'c',
    'why': 'y',
    'you': 'u'
}


def change_words_to_characters_and_numbers(sentence: str):
    """
    Function changes words to characters and numbers based on defined dicts of:
        STRINGS_TO_NUMBERS
        STRINGS_MISTAKES_TO_NUMBERS
        STRINGS_MISTAKES_TO_CHARACTERS

    :param sentence: string, to change words to characters and numbers.
    :return: string, with changed words to characters and numbers.
    """

    # Change words to numbers.
    sentence = strings.replace_words_with_values_from_dict(sentence, STRINGS_TO_NUMBERS, True)
    # Change words with mistakes to numbers.
    sentence = strings.replace_words_with_values_from_dict(sentence, STRINGS_MISTAKES_TO_NUMBERS, True)
    # Change words with mistakes to characters.
    sentence = strings.replace_words_with_values_from_dict(sentence, STRINGS_MISTAKES_TO_CHARACTERS, True)

    return sentence


def get_text_from_wav(wav_file_path: str, engine: str = "google", adjust_for_ambient_noise: bool = False) -> str:
    """
    The function recognizes speech in source WAV file and returns recognized text.

    :param wav_file_path: string, full file path to WAV file.
    :param engine: string, offline speech recognition engine, default is 'google'. Available engines:
        'google', 'sphinx', 'tensorflow', 'whisper', 'vosk'.
    :param adjust_for_ambient_noise: bool, if True, will adjust for ambient noise before recognizing.
        Default is False.
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
        # If 'adjust_for_ambient_noise' is True, will adjust for ambient noise before recognizing.
        if adjust_for_ambient_noise:
            speech_recognizer.adjust_for_ambient_noise(source)

        audio = speech_recognizer.record(source)
    # Convert to text.
    # When using 'recognize_google' it outputs debugging JSON, there's an option 'show_all=False',
    # which is set by default, could be a bug in current version 3.9.0. There are some changes in GitHub for it
    # but not in PyPi, will wait.

    text = str()
    if engine == "google":
        text = speech_recognizer.recognize_google(audio)
    elif engine == "sphinx":
        # pip install pocketsphinx
        text = speech_recognizer.recognize_sphinx(audio)
    elif engine == "tensorflow":
        # pip install tensorflow
        text = speech_recognizer.recognize_tensorflow(audio)
    elif engine == "whisper":
        # pip install torch
        # pip install whisper
        text = speech_recognizer.recognize_whisper(audio)
    elif engine == "vosk":
        # pip install vosk
        text = speech_recognizer.recognize_vosk(audio)

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
    temp_file_mp3.file_path = download(audio_file_url, temp_file_mp3.directory)
    # Add the file path to wav temp file including extension '.wav'.
    temp_file_wav.file_path = temp_file_mp3.file_path + ".wav"

    # Convert the file from mp3 to wav, since speech_recognition module works with wav files and get text.
    text = convert_mp3_and_get_text(temp_file_mp3.file_path, temp_file_wav.file_path)

    # Remove temp files.
    temp_file_mp3.remove()
    temp_file_wav.remove()

    return text

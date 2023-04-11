import io
import queue
import threading

from .print_api import print_api, print_status
from .wrappers import numpyw
from .basics import numbers

import soundcard
import soundfile
import pythoncom


def get_inputs(include_loopback: bool = False, **kwargs):
    """
    The function will return all the input interfaces currently available to 'soundcard' library.

    :param include_loopback: boolean, the default is 'False'.
        True: include also all the loopback input interfaces.
        False: do not include also all the loopback input interfaces.
    :param kwargs: for 'print_api'.
    :return: list, of input interfaces.
    """

    # Get all the input interfaces,
    inputs = soundcard.all_microphones(include_loopback=include_loopback)

    # Iterate through all the interfaces and output them to console with indexes.
    for index, interface in enumerate(inputs):
        print_api(f'[{index}]: {interface} | Loopback: {interface.isloopback}', **kwargs)
    return inputs


def get_outputs(**kwargs):
    """
    The function will return all the output interfaces currently available to 'soundcard' library.

    :param kwargs: for 'print_api'.
    :return: list, of output interfaces.
    """

    # Get all the output interfaces,
    outputs = soundcard.all_speakers()
    # Iterate through all the interfaces and output them to console with indexes.
    for index, interface in enumerate(outputs):
        print_api(f'[{index}]: {interface}', **kwargs)
    return outputs


def get_default_input(**kwargs):
    """
    The function will get the default input.
    :param kwargs: for 'print_api'.
    :return: input interface object of 'soundcard' library.
    """

    try:
        # Get the default input interface. If there is no default interface configured in the system, you will get
        # an exception.
        default_input = soundcard.default_microphone()
    except RuntimeError as exception_object:
        default_input = f'NONE [{exception_object}]'
    print_api(f'Default Input: {default_input}', **kwargs)
    return default_input


def get_default_output(**kwargs):
    """
    The function will get the default output.
    :param kwargs: for 'print_api'.
    :return: output interface object of 'soundcard' library.
    """

    default_output = soundcard.default_speaker()
    print_api(f'Default Output: {default_output}', **kwargs)
    return default_output


def get_loopback_inputs(first: bool = False, select_interface=None, **kwargs):
    """
    The function will return all input interfaces that support loopback feature.

    :param first: boolean, return only the first input loopback interface.
    :param select_interface: None / integer,
        None: no interface will be selected.
        int: the index of the loopback input interface. Meaning, '0' will select the first interface from the interface
            list and the function will return list with single interface object.
    :param kwargs: parameters for 'print_api'.
    :return: list, of loopback input interfaces.
    """

    # Get the list of all available inputs including loop-backs, since we want to record from a loopback.
    input_interfaces = get_inputs(include_loopback=True, stdout=False)

    # Iterate through all the input interfaces.
    input_loopback_list: list = list()
    for input_interface in input_interfaces:
        # If loopback setting is 'True' on current interface iteration.
        if input_interface.isloopback:
            # Add this interface to the list.
            input_loopback_list.append(input_interface)
            # If 'first' set is set to 'True' then we break the loop, since we found the first one.
            if first:
                break

    # If loopback input interfaces were found.
    if input_loopback_list:
        # Iterate through akk the loopback interfaces with index.
        for index, loopback_interface in enumerate(input_loopback_list):
            # If 'select_interface' is an integer and not 'None',
            # print to console the interface with index and 'SELECTED'.
            if isinstance(select_interface, int):
                print_api(f'Found Loopback:\n'
                          f'[{index}]: {loopback_interface} | SELECTED', **kwargs)
            # If 'select_interface' is 'None'.
            else:
                print_api(f'Found Loopback:\n'
                          f'[{index}]: {loopback_interface}', **kwargs)
    # If no loopback input interfaces were found.
    else:
        print_api('No Loopback Input interfaces were found.')

    # If 'input_loopback_list' is not empty (loopback interfaces were found) and 'select_interface' is an integer
    # and not 'None', then return a list with selected interface only.
    if input_loopback_list and isinstance(select_interface, int):
        input_loopback_list = [input_loopback_list[select_interface]]

    return input_loopback_list


def open_byteio_soundfile(samplerate: int = 44100, bit_rate: str = 'PCM_16'):
    byte_io = io.BytesIO()
    # In order for the 'soundfile' library to recognize the 'io.BytesIO' object as a file,
    # we need to give it a name with extension of '.wav'.
    # byte_io.name = 'test.wav'
    # Or we can use the "format='WAV'" parameter.
    output_memory = soundfile.SoundFile(
        byte_io, mode='w', samplerate=samplerate, channels=2, subtype=bit_rate, format='WAV')

    return output_memory


def close_byteio_soundfile():
    return


class ByteIOSoundFile:
    def __init__(self, samplerate: int = 44100, bit_rate: str = 'PCM_16', return_type: str = 'file'):
        """

        :param samplerate: int, default 44100.
        :param bit_rate: str, default 'PCM_16'.
        :param return_type: string, return type of the 'ByteIOSoundFile' object on 'close()' method.
            Default is 'file'. Available:
                'file' - return the 'io.BytesIO' object.
                'bytes' - return the 'io.BytesIO' object as bytes.
        """

        self.samplerate: int = samplerate
        self.bit_rate: str = bit_rate
        self.return_type: str = return_type

        self.byte_io = None
        self.output_memory = None

    def open(self):
        self.byte_io = io.BytesIO()
        # In order for the 'soundfile' library to recognize the 'io.BytesIO' object as a file,
        # we need to give it a name with extension of '.wav'.
        # byte_io.name = 'test.wav'
        # Or we can use the "format='WAV'" parameter.
        self.output_memory = soundfile.SoundFile(
            self.byte_io, mode='w', samplerate=self.samplerate, channels=2, subtype=self.bit_rate, format='WAV')

    def write(self, data):
        self.output_memory.write(data)

    def close(self):
        self.output_memory.close()
        self.byte_io.seek(0)

        if self.return_type == 'file':
            # Return the 'io.BytesIO' object as is.
            return self.byte_io
        elif self.return_type == 'bytes':
            # Convert the 'io.BytesIO' object to bytes.
            return self.byte_io.read()


class StereoMixRecorder:
    def __init__(
            self, samplerate: int = 44100, bit_rate: str = 'PCM_16', buffer_size: int = 1024,
            skip_empty_buffers: bool = False, use_first_loopback: bool = True, select_interface=None):
        """
        :param samplerate: integer, sample rate of the wave that will be recorded. The default is '44100', since regular
            audio wav files for listening are this quality.
        :param bit_rate: string, the bit rate of the wave that will be recorded. The default is 'PCM_16'.
            The string represents 'subtype' option of 'soundfile' library. Currently supported:
                'PCM_S8':         0x0001,  # Signed 8-bit data
                'PCM_16':         0x0002,  # Signed 16-bit data
                'PCM_24':         0x0003,  # Signed 24 bit data
                'PCM_32':         0x0004,  # Signed 32-bit data
                'PCM_U8':         0x0005,  # Unsigned 8-bit data (WAV and RAW only)
                'FLOAT':          0x0006,  # 32-bit float data
                'DOUBLE':         0x0007,  # 64-bit float data
                'MPEG_LAYER_III': 0x0082,  # MPEG-2 Audio Layer III.
                * More options are available in 'soundfile' library.
        :param buffer_size: integer, amount of frames / samples to record at once. The default is '1024'.
        :param skip_empty_buffers: boolean, skip empty buffers. The default is 'False' - do not skip.
            Each buffer contains 'buffer_size' amount of frames / samples. If the buffer is empty, it means that there
            was no sound in the input interface and all the frames came as zeroes.
        :param use_first_loopback: boolean, get the first loopback input interface that was found.
        :param select_interface: None / integer, select the interface from the input loopback interfaces list.
        """

        self.samplerate: int = samplerate
        self.bit_rate: str = bit_rate
        self.buffer_size: int = buffer_size
        self.skip_empty_buffers: bool = skip_empty_buffers
        self.use_first_loopback: bool = use_first_loopback
        self.select_interface: int = select_interface

        self.recording: bool = False
        self.loopback_input = None
        self._buffer_queue: queue.Queue = queue.Queue()
        self._some_data_was_recorded: bool = False

    def _initialize_input_interface(self):
        """
        The function will initialize the input interface.
        """

        # Get the loopback input. We need only one.
        loopback_inputs = get_loopback_inputs(first=self.use_first_loopback, input_interface=self.select_interface)

        # If more than 1 loopback interface was found.
        if len(loopback_inputs) > 1:
            raise RuntimeError("There can't be more than 1 input interface, use selection option.")
        # If no loopback interfaces were found.
        elif not loopback_inputs:
            raise RuntimeError("Loopback input interface wasn't found.")

        return loopback_inputs[0]

    def start(
            self, split_emit_buffers: int = None, emit_type: str = None, file_path: str = None,
            record_until_zero_array: bool = False, seconds: int = None, **kwargs):
        """
        The function will start recording from stereo mix loopback in the sound driver.

        :param split_emit_buffers: integer/None, amount of buffers to emit.
            The default is None.
            None: all the buffers will be emitted when record 'stop()'s.
            1: meaning that each buffer will be emitted as it enters from the 'soundcard' module.
            2: meaning that every 2 buffers will be emitted as one, etc.
        :param emit_type: string, the type of the emitted data through 'emit()' method. The default is None.
            Currently supported:
                None: no data will be emitted, meaning that 'emit()' method will be disabled.
                'byteio': 'io.BytesIO' object - file object that will contain the same data that is stored in actual
                    '.wav' file.
                'nparray': float64 numpy array.
        :param file_path: string, full file path to '.wav' file to save. Default is None, meaning that no file
            will be saved.
        :param record_until_zero_array: boolean, record until the numpy array output from 'record()' method
            is all zeros. The default is 'False'.
            This happens when nothing is playing in the stereo mix.
            If this parameter is 'True', the recording will stop when the playback in stereo mix will stop.
        :param seconds: integer, amount of seconds to record. The default is None, meaning that the recording will
            continue until the 'stop()' method is called.
        :param kwargs:
        :return:
        """

        if not file_path and not emit_type:
            raise ValueError("Either 'file_path' or 'emit_type' must be specified.")

        self.recording = True
        threading.Thread(
            target=self._thread_record,
            args=(split_emit_buffers, emit_type, file_path, record_until_zero_array, seconds),
            kwargs=kwargs
        ).start()

    def _thread_record(
            self, split_emit_buffers: int, emit_type: str, file_path: str, record_until_zero_array: bool, seconds,
            **kwargs):
        # Since, 'soundcard' module uses COM objects, which aren't thread safe, we need to use 'CoInitialize()' of
        # COM objects in order for it to be. Or you will get an exception:
        # RuntimeError: Error 0x800401f0
        # The error code 0x800401F0 is CO_E_NOTINITIALIZED ("CoInitialize has not been called").
        # That suggests that you did not call CoInitialize() first. That is, a thread needs to call CoInitialize()
        # (or CoInitializeEx() ) before calling CoCreateInstance() or any other COM call.
        # When thread is finished, it should call CoUninitialize() to release the thread's COM resources.
        # noinspection PyUnresolvedReferences
        pythoncom.CoInitialize()

        self.loopback_input = self._initialize_input_interface()

        # Currently no frames were recorded.
        recorded_frames = 0

        # If the 'file_path' was specified, then wav file will be written to it.
        output_file = None
        if file_path:
            output_file = soundfile.SoundFile(
                file_path, mode='w', samplerate=self.samplerate, channels=2, subtype=self.bit_rate)

        # If the 'emit_type' of 'byteio' was specified, then the data will be emitted as 'io.BytesIO' object,
        # containing bytes of the recorded audio as WAV.
        byteio_soundfile = None
        data_nparray_buffer_list = None
        if emit_type == 'byteio':
            byteio_soundfile = ByteIOSoundFile(self.samplerate, self.bit_rate)
            byteio_soundfile.open()
        elif emit_type == 'nparray':
            data_nparray_buffer_list = list()

        total_frames = None
        if seconds:
            # Getting the total number of buffers.
            total_frames = seconds * self.samplerate

            # If the total amount of frames is not divisible by the buffer size, this means that the last buffer
            # will be smaller than the rest of the buffers. To avoid this, we will add the buffer size to the total
            # amount of frames, so that the last buffer will be the same size as the rest of the buffers.

            # To do that we'll divide the total amount of frames by the buffer size, to know how many buffers there
            # are, this number will be converted to int to drop all the numbers after the '.' dot.
            # Then multiply it by the buffer size, to get the total amount of frames without the last buffer.
            # Then add the buffer size to get the total amount of frames with the last buffer.
            if not numbers.is_divisible(total_frames, self.buffer_size):
                total_frames = int(total_frames/self.buffer_size)*self.buffer_size + self.buffer_size

            message = f"Record will stop after: [{seconds}] Seconds, [{total_frames}] Frames"
            print_api(message)

        emit_buffers_counter = 0
        # Use first input interface (with only 1 interface in the list at this stage).
        with self.loopback_input.recorder(samplerate=self.samplerate) as input_interface:
            # Record while the amount of recorded frames is not equal to the final total amount of frames.
            while self.recording:
                # If the 'seconds' parameter was specified, and the total amount of recorded frames is equal to
                # the total amount of frames, then stop recording.
                if seconds and recorded_frames == total_frames:
                    self.stop()

                emit_buffers_counter += 1
                # print(emit_buffers_counter)
                # Record audio data from selected loopback input interface for 'buffer_size' amount of frames.
                data_nparray = input_interface.record(numframes=self.buffer_size)

                # Aggregating the total amount of recorded frames as integer.
                recorded_frames = recorded_frames + self.buffer_size

                # If 'record_until_zero_array' is 'True' and the buffer is empty, and some data was already present in
                # previous cycle - stop recording.
                if record_until_zero_array and self._some_data_was_recorded and numpyw.is_array_empty(data_nparray):
                    self.stop()

                # If 'skip_empty_buffers' is 'True' and the buffer is empty, skip it.
                if self.skip_empty_buffers and numpyw.is_array_empty(data_nparray):
                    print_status(True, 'Skipping Empty Frames', recorded_frames, None, color="yellow")
                # If the buffer is not empty, write it to the wave file.
                else:
                    # If the buffer is not empty, set the flag to 'True'.
                    if not numpyw.is_array_empty(data_nparray):
                        self._some_data_was_recorded = True

                    # Write the data to the file and/or to the memory ByteIO object/numpy array list.
                    if file_path:
                        output_file.write(data_nparray)

                    if emit_type == 'byteio':
                        byteio_soundfile.write(data_nparray)
                    elif emit_type == 'nparray':
                        data_nparray_buffer_list.append(data_nparray)

                    print_status(
                        True,
                        'Recorded: Seconds | Frames: ', f'[{recorded_frames / self.samplerate} | {recorded_frames}]',
                        None, suffix_string='         ', **kwargs)

                    # If the 'split_emit_buffers' was specified, emit the data in chunks.
                    if split_emit_buffers:
                        # If the counter reached the split amount, emit the data.
                        if emit_buffers_counter == split_emit_buffers:
                            # Reset the counter.
                            emit_buffers_counter = 0

                            if emit_type == 'byteio':
                                # Emit the data and close the SoundFile and ByteIO object.
                                emit_bytes = byteio_soundfile.close()
                                self._buffer_queue.put(emit_bytes)
                                # Open new SoundFile and ByteIO object.
                                byteio_soundfile.open()
                            elif emit_type == 'nparray':
                                # If 'split_emit_buffers' is 1, then emit the data as is.
                                if split_emit_buffers == 1:
                                    self._buffer_queue.put(data_nparray)
                                # If 'split_emit_buffers' is more than 1, then concatenate the list of data arrays
                                # and emit it.
                                else:
                                    self._buffer_queue.put(numpyw.concatenate_array_list(data_nparray_buffer_list))
                                    # Clear the list.
                                    data_nparray_buffer_list = list()

        # ==============================================================================================================
        # At this point the recording has stopped.

        # If the 'file_path' was specified, then rest of the wav file will be written to it.
        if file_path:
            output_file.close()
        # If the 'emit_type' of 'byteio' was specified, then the data will be emitted as 'io.BytesIO' object,
        # and emit to buffer queue.
        if emit_type == 'byteio':
            emit_bytes = byteio_soundfile.close()
            self._buffer_queue.put(emit_bytes)
        elif emit_type == 'nparray':
            self._buffer_queue.put(numpyw.concatenate_array_list(data_nparray_buffer_list))

        # Release the COM object in multithreaded environment when thread is finished.
        # noinspection PyUnresolvedReferences
        pythoncom.CoUninitialize()

    def stop(self):
        """
        The function will stop recording from stereo mix loopback in the sound driver.

        :return: None.
        """

        self.recording = False

    def emit(self):
        """
        The function will emit the data that was recorded.
        Blocking function, since it will wait until data is available by using queue.Queue object
        'self._buffer_queue.get()'.

        If 'emit_type' is 'byteio', the function will return 'bytes' object (contains WAV file) that was extracted
        from 'io.BytesIO' object.
        If 'emit_type' is 'nparray', the function will return 'float64' numpy array.

        :return: 'bytes' wav file object or 'float64' numpy array.
        """

        return self._buffer_queue.get()


"""
Recording comments:
1. Tried to use 'wave' built-in library, It can write buffer chunks to wave file - you don't have to write
the whole numpy array at once. Since, 'soundcard' library returns 'float64' numpy array, you have to convert
it to 'int16' numpy array before recording it to wave file or you will get noise while saving to 16 bit wave file.
Only after converting to 'int16' numpy array, you can convert numpy array to bytes and write it to wave file.
This gave me clipped distorted wave file for some reason.

Usage:
import wave
with wave.open(file_path, "w") as output_file:
    # 2 Channels.
    output_file.setnchannels(2)
    # Sample width is bit rate, just in bytes. Meaning, 16-bit bitrate is 2 bytes samplewidth.
    # output_file.setsampwidth(2)
    # Or you can just divide the bitrate by 8, to get bytes for sample width.
    output_file.setsampwidth(bitrate/8)
    output_file.setframerate(samplerate)
    
    # Recording loop.
    while True:
        # Get the float64 numpy array of recorded data.
        data = input_interface.record(numframes=buffer_size)
        # Convert the numpy array to int16 numpy array.
        data = numpyw.convert_float64_to_int16(data)
        # Write the data to wave file, while converting numpy array to bytes.
        output_file.writeframes(numpyw.convert_array_to_bytes(data))
        
2. Tried to use 'scipy.io.wavfile.write', this worked fine, but it requires the whole numpy array to be recorded
at once. Scipy doesn't support writing buffer chunks to wave file. And, the same applies here, you have to convert
the 'float64' numpy array to 'int16' numpy array before recording it to wave file or you will get noise while 
saving to 16 bit wave file.

Usage:
from scipy.io.wavfile import write

# 'buffer_list' will store the recorded data.
buffer_list: list = list()

# Recording loop.
while True:
    # Get the float64 numpy array of recorded data.
    data = input_interface.record(numframes=buffer_size)
    # Convert the numpy array to int16 numpy array.
    data = numpyw.convert_float64_to_int16(data)
    # Append the data to buffer list.
    buffer_list.append(data)
    
# Concatenate the numpy arrays in the buffer list.
concatenated_numpy_array = numpyw.concatenate_numpy_arrays(buffer_list)
# Write the wave file with 'scipy'.
write(file_path, samplerate, concatenated_numpy_array)

3. Finally 'soundfile' library, was the only one that converts the 'float64' numpy array to 'int16' numpy array
automatically, and also supports writing buffer chunks to wave file. So, this is the best option. 
"""

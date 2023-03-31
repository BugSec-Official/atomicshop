# v1.0.0 - 31.03.2023 17:10
from .print_api import print_api, print_status
from .wrappers import numpyw

import soundcard
import soundfile


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


def record_stereo_mix(
        file_path: str, seconds: int, buffer_size: int = 1024, samplerate: int = 44100, bit_rate: str = 'PCM_16',
        skip_empty_buffers: bool = False, use_first_loopback: bool = True, select_interface=None, **kwargs):
    """
    The function will record from stereo mix loopback in the sound driver for specified amount of time.

    :param file_path: string, full file path to '.wav' file to save.
    :param seconds: integer, amount of seconds to record.
    :param buffer_size: integer, amount of frames / samples to record at once. The default is '1024'.
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
    :param skip_empty_buffers: boolean, skip empty buffers. The default is 'False' - do not skip.
        Each buffer contains 'buffer_size' amount of frames / samples. If the buffer is empty, it means that there
        was no sound in the input interface and all the frames came as zeroes.
    :param use_first_loopback: boolean, get the first loopback input interface that was found.
    :param select_interface: None / integer, select the interface from the input loopback interfaces list.
    :param kwargs: parameters for 'print_api'.
    :return: None.
    """

    # Get the loopback input. We need only one.
    loopback_inputs = get_loopback_inputs(first=use_first_loopback, input_interface=select_interface)

    # If more than 1 loopback interface was found.
    if len(loopback_inputs) > 1:
        raise RuntimeError("There can't be more than 1 input interface, use selection option.")
    # If no loopback interfaces were found.
    elif not loopback_inputs:
        raise RuntimeError("Loopback input interface wasn't found.")

    # Getting the total number of buffers.
    total_frames = seconds * samplerate
    # Currently no frames were recorded.
    recorded_frames = 0

    with soundfile.SoundFile(file_path, mode='w', samplerate=samplerate, channels=2, subtype=bit_rate) as output_file:
        # Use first input interface (with only 1 interface in the list at this stage).
        with loopback_inputs[0].recorder(samplerate=samplerate) as input_interface:
            message = f'Recording Seconds: [{seconds}]. ' \
                      f'Buffer size (frames): [{buffer_size}]. ' \
                      f'Total Frames: [{total_frames}].'
            print_api(message, **kwargs)

            # Record while the amount of recorded frames is not equal to the final total amount of frames.
            while recorded_frames != total_frames:
                frames_left = total_frames - recorded_frames
                same_line = True
                # If the amount of frames left is less than the buffer size that was set in the beginning,
                # it means that we are in the last buffer, and we need to set the buffer size to the amount of frames
                # left and also set 'same_line' to 'False' so that the prints after that will be printed in a new line.
                if frames_left <= buffer_size:
                    same_line = False
                    buffer_size = frames_left

                # Record audio data from selected loopback input interface for 'buffer_size' amount of frames.
                data = input_interface.record(numframes=buffer_size)

                recorded_frames = recorded_frames + buffer_size

                # If 'skip_empty_buffers' is 'True' and the buffer is empty, skip it.
                if skip_empty_buffers and numpyw.check_if_array_is_empty(data):
                    print_status(same_line, 'Skipping Empty Frames', recorded_frames, total_frames, color="yellow")
                # If the buffer is not empty, write it to the wave file.
                else:
                    output_file.write(data)
                    print_status(same_line, 'Recorded Frames', recorded_frames, total_frames, suffix_string='         ')

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

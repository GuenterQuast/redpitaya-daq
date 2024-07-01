import numpy as np

def clipping(input_data, clipping_level):
    """
    Check if any channel in the input data exceeds the clipping level.

    Args:
        input_data (ndarray): The input data to check for clipping.
        clipping_level (float or dict): The clipping level to check against. If a float is provided, it will be applied to all channels.
                                        If a dictionary is provided, it should contain upper and lower clipping levels for each channel.

    Returns:
        bool or ndarray:  returns the input_data.
    """
    if isinstance(clipping_level, float):
        clipping_level = {channel: {'upper': clipping_level, 'lower': -clipping_level} for channel in input_data.dtype.names}
    elif isinstance(clipping_level, dict):
        for channel in input_data.dtype.names:
            if isinstance(clipping_level[channel], float):
                clipping_level[channel] = {'upper': clipping_level[channel], 'lower': -clipping_level[channel]}
    for channel in input_data.dtype.names:
        if np.max(input_data[channel]) >= clipping_level[channel]['upper'] or np.min(input_data[channel]) <= clipping_level[channel]['lower']:
            return None
    return input_data

def coincidence(peaks, coincidence_window, trigger_channel):
    """
    Check if any channel has a peak within the specified coincidence window.

    Args:
        peaks (dict): A dictionary containing the peak data for each channel.
        coincidence_window (int): The maximum distance between peaks for them to be considered coincident.
        trigger_channel (str): The channel to use as the trigger.

    Returns:
        peaks or None: peaks if any channel has a peak within the coincidence window, None otherwise.
    """
    if len(peaks) == 0:
        return None
    for key in peaks.keys():
        if key != trigger_channel and len(peaks[key]) > 0 and abs(peaks[key][0] - peaks[trigger_channel][0]) <= coincidence_window:
            return peaks
    return None

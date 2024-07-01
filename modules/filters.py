import numpy as np

def clipping(input_data, clipping_config):
    """
    Check if any channel in the input data exceeds the clipping level.


    Currently clipping_config is a float, can be later eddited to be a dict if more requirements are neccesary
    Args:
        input_data (ndarray): The input data to check for clipping.
        clipping_level (float): The clipping level to check against.

    Returns:
        ndarray:  returns the input_data.
    """
    for channel in input_data.dtype.names:
        if np.max(input_data[channel]) >= clipping_config or np.min(input_data[channel]) <= -clipping_config:
            return None
    return input_data

def coincidence(peaks, coincidence_config, trigger_channel):
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
        if key != trigger_channel and abs(peaks[key][0] - peaks[trigger_channel][0]+coincidence_config['offset']) <= coincidence_config['width']:
            return peaks
    return None

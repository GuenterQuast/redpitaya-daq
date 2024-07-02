from scipy import signal
import numpy as np

def tag_peaks(input_data, peak_config):
    peaks = {}
    peaks_prop = {}
    for key in input_data.dtype.names:
        peaks[key], peaks_prop[key] = signal.find_peaks(
            input_data[key], prominence=peak_config['prominence'], distance=peak_config['distance'], width=peak_config['width']
        )
    return peaks, peaks_prop

# Pulse height detection like Pavels algorhythm
def find_rightmost_value_before_index(arr, i, min_value):
    """
    Find the rightmost value in the array `arr` that is less than or equal to `min_value`
    before the given index `i`.

    Args:
        arr (array-like): The input array.
        i (int): The index to search before.
        min_value (float): The minimum value to compare against.

    Returns:
        int: The index of the rightmost value that satisfies the condition, or -1 if no such value is found.
    """
    
    if i < 0 or i > len(arr):
        return -1  # return -1 if i is out of the array bounds
    
    # Convert to numpy array if not already
    arr = np.array(arr)
    
    # Get indices where the value is less than or equal to min_value
    valid_indices = np.where(arr[:i] <= min_value)[0]
    
    if valid_indices.size == 0:
        return -1  # No values less than or equal to min_value found before index i
    
    return valid_indices[-1]


def pulse_height_pavel(input_data, pulse_height_pavel_config):
    peaks, peaks_prop = tag_peaks(input_data, pulse_height_pavel_config['peak_config'])
    heights = []
    start_positions = []
    for key in input_data.dtype.names:
        for peak, left_ips in zip(peaks[key], peaks_prop[key]['left_ips']):
            start_position = find_rightmost_value_before_index(np.gradient(input_data[key]), int(left_ips), pulse_height_pavel_config['gradient_min_value'])
            if start_position != -1:
                heights.append(input_data[key][peak] - input_data[key][start_position])
                start_positions.append(start_position)
        peaks_prop[key]['height'] = heights
        peaks_prop[key]['start'] = start_positions
    return peaks, peaks_prop
        
# <--- End Pulse height detection like Pavel


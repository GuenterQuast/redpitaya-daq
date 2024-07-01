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
def find_rightmost_zero_before_index(arr, i):
    if i < 0 or i > len(arr):
        return -1  # return -1 if i is out of the array bounds
    
    # Convert to numpy array if not already
    arr = np.array(arr)
    
    # Get indices where the value is 0
    zero_indices = np.where(arr[:i] == 0)[0]
    
    if zero_indices.size == 0:
        return -1  # No zeros found before index i
    
    return zero_indices[-1]


def pulse_height_pavel(input_data, pulse_height_pavel_config):
    peaks, peaks_prop = tag_peaks(input_data, pulse_height_pavel_config['peak_config'])
    heights = []
    for key in input_data.dtype.names:
        for peak, peak_prop in zip(peaks[key], peaks_prop[key]):
            start_position = find_rightmost_zero_before_index(np.gradient(input_data[key]), peak_prop['left_ips'])
            if start_position != -1:
                heights.append(input_data[key][peak] - input_data[key][start_position])
        peaks_prop[key]['height'] = heights
        
        



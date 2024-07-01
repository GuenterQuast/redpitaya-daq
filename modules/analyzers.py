from scipy import signal

def tag_peaks(input_data, peak_config):
    peaks = {}
    peaks_prop = {}
    for key in input_data.dtype.names:
        peaks[key], peaks_prop[key] = signal.find_peaks(
            input_data[key], prominence=peak_config['prominence'], distance=peak_config['distance'], width=peak_config['width']
        )
    return peaks, peaks_prop


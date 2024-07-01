from scipy import signal

def tag_peaks(input_data, prominence, distance, width):
    peaks = {}
    peaks_prop = {}
    for key in input_data.dtype.names:
        peaks[key], peaks_prop[key] = signal.find_peaks(
            input_data[key], prominence=prominence, distance=distance, width=width
        )
    return peaks, peaks_prop


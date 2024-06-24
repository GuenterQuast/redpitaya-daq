import numpy as np

def import_data(filename, number_of_samples, channel_names):
    """
    Convert recorded pulses into a structured array, similar to how it would be handled by mimoCorb.

    Parameters:
    filename (str): Path to the file containing the recorded pulse data.
    number_of_samples (int): Number of samples to consider for each channel.
    channel_names (list): List of channel names.

    Returns:
    np.ndarray: Structured array containing the recorded pulse data.
    """
    # Load the data from the file using memory mapping to handle large files efficiently
    data = np.load(filename, mmap_mode='r')
    
    # Define the data type for each channel with the given number of samples
    dtype_sample = f'{number_of_samples}int16'
    dtype = np.dtype([(channel, dtype_sample) for channel in channel_names])
    
    # Initialize the structured array with the correct dtype
    structured_data = np.zeros(len(data), dtype=dtype)
    
    # Populate the structured array with data
    for i, record in enumerate(data):
        for j, channel in enumerate(channel_names):
            structured_data[i][channel] = record[j][:number_of_samples]
    
    # Print the number of recorded triggers
    print("Data read successfully, recorded triggers =", structured_data.size)
    
    return structured_data, structured_data.size
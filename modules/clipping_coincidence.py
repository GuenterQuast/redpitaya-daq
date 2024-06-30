"""Module **pulse_filter** 

This (rather complex) module filters waveform data to search for valid signal pulses. 
The code first validates the trigger pulse, identifies coincidences of signals in 
different layers (indiating the passage of a cosmic ray particle, a muon) and finally
searches for double-pulse signatures indicating that a muon was stopped in or near 
a detection layer where the resulting decay-electron produced a delayed pulse. 
The time difference between the initial and the delayed pulses is the individual 
lifetime of the muon.

The decay time and the properties of the signal pulses (height, integral and 
postition in time) are written to a buffer; the raw wave forms are optionally
also written to another buffer. 

The callable functions *find_peaks()* and *calulate_decay_time()* depend on the 
buffer manager *mimoCoRB* and provide the filter functionality described above. 
These functions support multiple sinks to be configured for output. 

The relevant configuration parameters can be found in the section *find_peaks:* 
and *calculate_decay_time:* in the configuration file. 

""" 

from mimocorb.buffer_control import rbTransfer
import numpy as np
import pandas as pd
import os, sys

from filters import *

def filter(source_list=None, sink_list=None, observe_list=None, config_dict=None, **rb_info):
    """filter client for mimoCoRB: Find valid signal pulses in waveform data

       Input: 

        - wave form data from source buffer defined in source_list

       Returns: 
  
         - None if filter not passed
         - list of list(s) of pulse parameters, written to sinks defined in sink_list

    """
    
    if config_dict is None:
        raise ValueError("ERROR! Wrong configuration passed (in lifetime_modules: calculate_decay_time)!!")

    # Load configuration
    clipping_level = config_dict['clipping_level']
    peak_config = config_dict['peak_config']
    coincidence_window = config_dict['coincidence_window']

    
    def tag_pulses(input_data):   
        """
        """
        # Check for clipping
        if check_for_clipping(input_data, clipping_level): return None
        # Find peaks
        peaks, peaks_properties = tag_peaks(input_data, peak_config)
        # Only consider events with one peak per channel
        for key in peaks.keys():
            if len(peaks[key]) != 1:
                return None
        # Check for coincidences
        if not check_for_coincidence(peaks, coincidence_window): return None
        return input_data
        
    

    p_filter = rbTransfer(source_list=source_list, sink_list=sink_list, config_dict=config_dict,
                        ufunc=tag_pulses, **rb_info)
    p_filter()

if __name__ == "__main__":
    print("Script: " + os.path.basename(sys.argv[0]))
    print("Python: ", sys.version, "\n".ljust(22, '-'))
    print("THIS IS A MODULE AND NOT MEANT FOR STANDALONE EXECUTION")

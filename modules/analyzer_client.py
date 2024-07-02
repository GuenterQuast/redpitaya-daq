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
from analyzers import *

def analyzer(source_list=None, sink_list=None, observe_list=None, config_dict=None, **rb_info):
    """analyzer client for mimoCoRB: Find valid signal pulses in waveform data

       Input: 

        - wave form data from source buffer defined in source_list

       Returns: 
  
         - None if filter not passed
         - list of list(s) of pulse parameters, written to sinks defined in sink_list

    """
    
    if config_dict is None:
        raise ValueError("ERROR! Wrong configuration passed (in lifetime_modules: calculate_decay_time)!!")

    # Load configuration
    pulse_height_pavel_config = config_dict['pulse_height_pavel_config']
    list_of_channels = config_dict['list_of_channels']

    pulse_par_dtype = sink_list[-1]['dtype']
    
    def filter_waveform(input_data):   
        """
        Filters pulses in the input data.

        Args:
            input_data (list): The input data containing pulse information.

        Returns:
            list: The filtered input data.

        """
        peak_data= np.zeros( (1,), dtype=pulse_par_dtype)
        peaks,peaks_prop = pulse_height_pavel(input_data, pulse_height_pavel_config)
        for key in input_data.dtype.names:
            peak_data[0][key+'height'] = peaks_prop[key]['height']
        # this considers 
        peak_data[0]['Delta_T'] =  peaks[list_of_channels[0]][0]-peaks[list_of_channels[1]][0]
        
        
        return peak_data
        
    

    p_filter = rbTransfer(source_list=source_list, sink_list=sink_list, config_dict=config_dict,
                        ufunc=filter_waveform, **rb_info)
    p_filter()

if __name__ == "__main__":
    print("Script: " + os.path.basename(sys.argv[0]))
    print("Python: ", sys.version, "\n".ljust(22, '-'))
    print("THIS IS A MODULE AND NOT MEANT FOR STANDALONE EXECUTION")

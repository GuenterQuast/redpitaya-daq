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
import os
import sys

from filters import *


def find_peaks(source_list=None, sink_list=None, observe_list=None, config_dict=None, **rb_info):
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
    sample_time_ns = config_dict["sample_time_ns"]
    analogue_offset = config_dict["analogue_offset"] * 1000
    peak_minimal_prominence = config_dict["peak_minimal_prominence"]
    peak_minimal_distance = config_dict["peak_minimal_distance"]
    peak_minimal_width = config_dict["peak_minimal_width"]
    pre_trigger_samples = config_dict["pre_trigger_samples"]
    trigger_channel = config_dict["trigger_channel"]
    #    if trigger_channel not in ['A','B','C','D']:
    if trigger_channel not in ["1", "2"]:
        trigger_channel = None
    trigger_position_tolerance = config_dict["trigger_position_tolerance"]

    pulse_par_dtype = sink_list[-1]["dtype"]

    def tag_pulses(input_data):
        """find all valid pulses

        This function to be called by instance of class mimoCoRB.rbTransfer

           Args:  input data as structured ndarray

           Returns: list of parameterized pulses
        """

        # Find all the peaks and store them in a dictionary
        peaks, peaks_prop = tag_peaks(input_data, peak_minimal_prominence, peak_minimal_distance, peak_minimal_width)

        # identify trigger channel, validate trigger pulse and get time of trigger pulse
        if trigger_channel is not None:
            trigger_peaks = peaks["ch" + trigger_channel]
            if len(trigger_peaks) == 0:
                return None
            reference_position = trigger_peaks[np.argmin(np.abs(trigger_peaks - pre_trigger_samples))]
        else:  # external or no trigger: set to nominal position
            reference_position = pre_trigger_samples

        peak_data = np.zeros((1,), dtype=pulse_par_dtype)
        for key in peaks.keys():
            for position, height, left_ips, right_ips in zip(
                peaks[key], peaks_prop[key]["prominences"], peaks_prop[key]["left_ips"], peaks_prop[key]["right_ips"]
            ):
                if np.abs(reference_position - position) < trigger_position_tolerance:
                    peak_data[0][key + "_position"] = position
                    peak_data[0][key + "_height"] = input_data[key][position] - analogue_offset  # height
                    left = int(np.floor(left_ips))
                    right = int(np.ceil(right_ips))
                    peak_data[0][key + "_integral"] = (
                        sum(input_data[key][left:right] - analogue_offset) * sample_time_ns * 1e-9 / 50 / 5
                    )
        return [peak_data]

    p_filter = rbTransfer(
        source_list=source_list, sink_list=sink_list, config_dict=config_dict, ufunc=tag_pulses, **rb_info
    )
    p_filter()


if __name__ == "__main__":
    print("Script: " + os.path.basename(sys.argv[0]))
    print("Python: ", sys.version, "\n".ljust(22, "-"))
    print("THIS IS A MODULE AND NOT MEANT FOR STANDALONE EXECUTION")

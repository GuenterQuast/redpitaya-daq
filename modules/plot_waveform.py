"""
**plot**: plotting waveforms from buffer using mimoCoRB.buffer_control.OberserverData
"""

import sys
import os
from mimocorb.plot_buffer import plot_buffer
import matplotlib

# select matplotlib frontend if needed
matplotlib.use("TkAgg")


def plot_waveform(source_list=None, sink_list=None, observe_list=None, config_dict=None, **rb_info):
    """
    Plot waveform data from mimiCoRB buffer

    :param input: configuration dictionary

      - plot_title: graphics title to be shown on graph
      - min_sleeptime: time between updates
      - sample_time_ns, channel_range, pretrigger_samples and analogue_offset
        describe the waveform data as for oscilloscope setup
    """

    pltbuf = plot_buffer(source_list, sink_list, observe_list, config_dict, **rb_info)
    pltbuf()


if __name__ == "__main__":
    print("Script: " + os.path.basename(sys.argv[0]))
    print("Python: ", sys.version, "\n".ljust(22, "-"))
    print("THIS IS A MODULE AND NOT MEANT FOR STANDALONE EXECUTION")

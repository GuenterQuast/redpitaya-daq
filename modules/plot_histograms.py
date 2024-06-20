"""
**plot_histograms**: histogram variable(s) from buffer using mimoCoRB.histogram_buffer 
"""
import sys
import os
from mimocorb.histogram_buffer import histogram_buffer
import matplotlib

# select matplotlib frontend if needed
matplotlib.use("TkAgg")


def plot_histograms(source_list=None, sink_list=None, observe_list=None, config_dict=None, **rb_info):
    """
    Online display of histogram(s) of variable(s) from mimiCoRB buffer

    :param input: configuration dictionary

    """
    histbuf = histogram_buffer(source_list, sink_list, observe_list, config_dict, **rb_info)
    histbuf()


if __name__ == "__main__":
    print("Script: " + os.path.basename(sys.argv[0]))
    print("Python: ", sys.version, "\n".ljust(22, "-"))
    print("THIS IS A MODULE AND NOT MEANT FOR STANDALONE EXECUTION")

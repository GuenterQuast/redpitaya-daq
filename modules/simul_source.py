"""
**simul_source**: a simple template for a mimoCoRB source to 
enter simulated wave form data in a mimoCoRB buffer.

Input data is provided as numpy-arry of shape (number_of_channels, number_of_samples).
"""

from mimocorb.buffer_control import rbImport
import numpy as np
import sys, time
from mimocorb.pulseSimulator import pulseSimulator

def simul_source(source_list=None, sink_list=None, observe_list=None, config_dict=None, **rb_info):
    """
    Generate simulated data and pass data to buffer

    The class mimocorb.buffer_control/rbImport is used to interface to the
    newBuffer and Writer classes of the package mimoCoRB.mimo_buffer

    This example may serve as a template for other data sources

    :param config_dict: configuration dictionary

      - events_required: number of events to be simulated or 0 for infinite
      - sleeptime: (mean) time between events
      - random: random time between events according to a Poission process
      - number_of_samples, sample_time_ns, pretrigger_samples and analogue_offset
        describe the waveform data to be generated (as for oscilloscope setup)

    Internal parameters of the simulated physics process (the decay of a muon)
    are (presently) not exposed to user.
    """

    events_required = 1000 if "eventcount" not in config_dict else config_dict["eventcount"]

    def yield_data():
        """generate simulated data, called by instance of class mimoCoRB.rbImport"""

        event_count = 0
        while events_required == 0 or event_count < events_required:
            pulse = dataSource(number_of_channels)
            # deliver pulse data and no metadata
            yield (pulse, None)
            event_count += 1

    dataSource = pulseSimulator(config_dict)
    simulsource = rbImport(config_dict=config_dict, sink_list=sink_list, ufunc=yield_data, **rb_info)
    number_of_channels = len(simulsource.sink.dtype)
    # possibly check consistency of provided dtype with simulation !

    # TODO: Change to logger!
    # print("** simul_source ** started, config_dict: \n", config_dict)
    # print("?> sample interval: {:02.1f}ns".format(osci.time_interval_ns.value))
    simulsource()

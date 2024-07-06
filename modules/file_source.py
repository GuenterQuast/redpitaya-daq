""" **external_source**: 
Template for data import in a mimoCoRB buffer from an external source

Input data is provided as a numpy-arry of shape (number_of_channels, number_of_samples).
"""

from mimocorb.buffer_control import rbImport
import numpy as np
import sys, time

# ->> define input module here:
from mimocorb.parquetReader import parquetReader
dataSource = parquetReader


def tar_parquet_source(source_list=None, sink_list=None, observe_list=None, config_dict=None, **rb_info):
    """
    General example for data import from external source  
    (here: generation of simulated data with module parquetReader)
    
    Uses class mimocorb.buffer_control/rbImport to interface to the
    newBuffer and Writer classes of the package mimoCoRB.mimo_buffer

    mimiCoRB interacts with this code via a generator (*yield_data()*), 
    which itself received data via the *__call__* function of the class
    *dataSource* providing the input data. Configuration parametes 
    in the dictionary *config_dict* are passed to this class during
    initialistation. Parameters of the configured buffers are set after 
    after initialisation.

    This example may serve as a template for other data sources
    """

    # define and instantiate external data source
    source = dataSource(config_dict)

    def yield_data():
        """provide data from file, function called by instance of class mimoCoRB.rbImport"""
        event_count = 0
        while True:
            data = source()
            # deliver pulse data (and no metadata; these are added by rbImport)
            yield (data, None)
            event_count += 1

    # get buffer configuration
    sink_dict = sink_list[0]
    number_of_channels = len(sink_dict["dtype"])
    number_of_values = sink_dict["values_per_slot"]
    channel_names = [sink_dict["dtype"][i][0] for i in range(number_of_channels)]
    # consistency check
    if "number_of_samples" not in config_dict:
        pass
    else: 
        if number_of_values != config_dict["number_of_samples"]:
            print("! Config Error: requested number of samples does not match buffer size !")
            sys.exit("requested number of samples does not match buffer size !")
    source.init(number_of_channels, number_of_values, channel_names)        

    # instantiate buffer manager interface
    rbImporter = rbImport(config_dict=config_dict, sink_list=sink_list, ufunc=yield_data, **rb_info)
    # print("** simulation_source ** started, config_dict: \n", config_dict)

    # start __call__ method of rbImport instance 
    rbImporter()

"""
**file_source**: Read waveform data from file
"""

from mimocorb.buffer_control import rbImport
import numpy as np
import sys, os, time

import pandas as pd
import pathlib
import tarfile

def tar_parquet_source(source_list=None, sink_list=None, observe_list=None,
                            config_dict=None, **rb_info):
    """
    Read real data from parquet in a tar file

    The class mimocorb.buffer_control/rbImport is used to interface to the
    newBuffer and Writer classes of the package mimoCoRB.mimo_buffer

    :param config_dict: configuration dictionary
  
      - path: (relative) path to source files in .tar, 
      - sleeptime: (mean) time between events
      - random: pick a random time between events according to a Poission process
      - number_of_samples, sample_time_ns, pretrigger_samples and analogue_offset
        describe the waveform data to be generated (as for oscilloscope setup) 

    Internal parameters of the simulated physics process (the decay of a muon) 
    are (presently) not exposed to user.         
    """
    
    # evaluate configuration dictionary
    supported_suffixes = ['.tar', '.gz', '.tgz', '.bz2']
    path = config_dict["path"]
    sleeptime = 0.10 if "sleeptime" not in config_dict \
        else config_dict["sleeptime"]
    random = False if "random" not in config_dict \
        else config_dict["random"]
    number_of_samples = config_dict["number_of_samples"]

    filenames = iter([os.path.join(path, f) for f in os.listdir(path) if \
                      os.path.isfile(os.path.join(path, f)) and \
                      pathlib.Path(f).suffix in supported_suffixes ])

    def yield_data():
        """
        Data generator to deliver raw pulse data from parquet files
        """

        f = next(filenames)
        #print("** file_source: opening file: ", f, 10*' ' + '\n')
        in_tar = tarfile.open(f, 'r:*') # open with transparent compression

        while True:   
            parquet = in_tar.next()
            if parquet is None:
               # open next file, if any
               try: 
                   f = next(filenames)
               except StopIteration:  
                   sys.exit()  # all files processed, exit
               # print("** file_source: opening file: ", f, 10*' ' + '\n')
               in_tar = tarfile.open(f, 'r:*') # open with transparent compression
               parquet = in_tar.next()
               if parquet is None:  # end of input data, exit
                   sys.exit()

            # introduce random wait to mimic true data flow
            if random: 
                time.sleep(-sleeptime*np.log(np.random.rand())) # random Poisson sleep time
            else:
                time.sleep(sleeptime)  # fixed sleep time
            try:
                pd_data = pd.read_parquet(in_tar.extractfile(parquet))
            except FileNotFoundError:
                print("Could not open '" + str(parquet) + "' in '"+ str(f) + "'")
                continue
          
            # data from file is pandas format, convert to array
            data = []
            for i in range(number_of_channels):
                chnam = chnams[i]
                data.append(pd_data[chnam].to_numpy())
            # deliver data and no metadata
            yield(data, None)                

            
    fs = rbImport(sink_list=sink_list, config_dict=config_dict,
                  ufunc = yield_data, **rb_info)
    number_of_channels = len(fs.sink.dtype)
    chnams = [fs.sink.dtype[i][0] for i in range(number_of_channels)]

    # TODO: Change to logger!
    # print("** tar_parquet_source ** started, config_dict: \n", config_dict)
    # print("?> sample interval: {:02.1f}ns".format(fs.time_interval_ns.value))
    fs()

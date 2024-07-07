#!/usr/bin/env python3
"""
**redP_mimoCoRB**: use mimoCoRB with the RedPitaya and redPoscdaq.py 

Input data is provided as numpy-arry of shape (number_of_channels, number_of_samples)
via callback of the __call__() function in class redP_mimoCoRB.

This script depends on redPdaq.py and is started as a sup-process within the mimoCoRB
framework. The detailed set-up of ring buffers and the associated funtions is specified
in a configuration file, *<name>_setup.yaml*. The process suite is started by running this 
script from the command line, possibly specifying the name of the configutation file
as an argument.  

As a demonstration, a configuration *demo_setup.yaml* is contained in this package to 
import waveforms from the RedPitaya, display a sub-set of the waveforms and perform
a pulse-height analysis with updating results shown as histograms. 
To run this example, connect the out1 of the RedPitaya to one or both of the inputs, 
type "./redP_mimoCoRB.py* to run the example and use the graphical interface to connect 
the RedPitaya to the network, start the pulse generator, and finally press the *StartDAQ" 
button in the  oscilloscope tag to start data transfer to the *mimiCoRB* input buffer. 

Stop data taking with the button "End run" in the *mimoCoRB* conotrol window to 
cleanly shut down all processes. 

Note that this script depends on additional code for the *mimoCoRB* peak finder
in the sub-directory *modules/* and a corresponding configuration file in 
subdirectory *config/*.
"""

import time
import sys
import redPdaq as rp
from mimocorb.buffer_control import rbPut

class redP_mimocorb():            
    """ Interface for redPoscdaq.py to the daq rinbuffer mimoCoRB 
    """    
    def __init__(self, source_list=None, sink_list=None, observe_list=None, config_dict=None,
                 **rb_info):
        # initialize mimoCoRB interface 
        self.rb_exporter = rbPut(config_dict=config_dict, sink_list=sink_list, **rb_info)
        self.number_of_channels = len(self.rb_exporter.sink.dtype)
        self.events_required = 1000 if "eventcount" not in config_dict else config_dict["eventcount"]

        self.event_count = 0
        self.active=True
    def __call__(self, data):
        """function called by redPoscdaq  
        """
        if (self.events_required == 0 or self.event_count < self.events_required) and self.active:
             # deliver pulse data and no metadata
             active = self.rb_exporter(data, None) # send data
             self.event_count += 1
        else:
             active = self.rb_exporter(None, None) # send None when done
             print("redPoscdaq exiting") 
             sys.exit()
           
def redP_to_rb(source_list=None, sink_list=None, observe_list=None, config_dict=None, **rb_info):
    """Main function, 
      executed as a multiprocessing Process, to pass data from the RedPitaya to a mimoCoRB buffer
 
      :param config_dict: configuration dictionary
        - events_required: number of events to be taken
        - number_of_samples, sample_time_ns, pretrigger_samples and analogue_offset
        - decimation index, invert flags, trigger mode and trigger direction for RedPitaya
    """

    # initialize mimocorb class
    rb_source= redP_mimocorb(config_dict=config_dict, sink_list=sink_list, **rb_info)
    #print("data source initialized")

    # start oscilloscope in callback mode
    #print("starting osci")
    rp.run_rpControl(callback=rb_source, conf_dict=config_dict)

if __name__ == "__main__":  # -------------------------------------- 
#run mimoCoRB data acquisition suite
  # the code below is idenical to the mimoCoRB script run_daq.py
    import argparse
    import sys, time
    from mimocorb.buffer_control import run_mimoDAQ

    # define command line arguments ...
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('filename', nargs='?', default = "demo_setup.yaml",
                    help = "configuration file")
    parser.add_argument('-v','--verbose', type=int, default=2,
                    help="verbosity level (2)")
    parser.add_argument('-d','--debug', action='store_true',
                    help="switch on debug mode (False)")
    # ... and parse command line input
    args = parser.parse_args()

    print("\n*==* script " + sys.argv[0] + " running \n")
    daq = run_mimoDAQ(args.filename, verbose=args.verbose, debug=args.debug)
    daq.setup()
    daq.run()
    print("\n*==* script " + sys.argv[0] + " finished " + time.asctime() + "\n")

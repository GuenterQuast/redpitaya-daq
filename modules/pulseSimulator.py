import numpy as np
import time

class pulseSimulator:
    """generate wavevorm data of typical pulses from particle detectors, 
       characterised by an exponential shape with parameters height and 
       mean length tau and a noise contribution. 
    """    
   
    def __init__(self, config_dict):
        # evaluate configuration dictionary providing settings of recording device 
        self.number_of_samples = config_dict["number_of_samples"]
        self.analogue_offset_mv = config_dict["analogue_offset"] * 1000.0
        self.trigger_level = 0. if "trigger_level" not in config_dict else config_dict["trigger_level"] - self.analogue_offset_mv
        self.sample_time_ns = config_dict["sample_time_ns"]
        self.pre_trigger_samples = config_dict["pre_trigger_samples"]
        self.events_required = 1000 if "eventcount" not in config_dict else config_dict["eventcount"]
        self.sleeptime = 0.10 if "sleeptime" not in config_dict else config_dict["sleeptime"]
        self.random = False if "random" not in config_dict else config_dict["random"]
        # parameters for pulse simulation and detector porperties 
        self.plen = 100 if "pulseWindow" not in config_dict else\
            config_dict["pulseWindow"]
        self.pulse_height = 250.0 if "pulseHeight" not in config_dict else\
            config_dict["pulseHeight"]
        self.pulse_spread = self.pulse_height * 0.3 if "pulseSpread" not in config_dict else\
            config_dict["pulseSpread"]
        self.tau = self.plen / 4.0  # decay time of exponential pulse
        self.mn_position = self.pre_trigger_samples
        self.mx_position = self.number_of_samples - self.plen
        self.pulse_template = np.exp(-np.float32(np.linspace(0.0, self.plen, self.plen, endpoint=False)) / self.tau)
        self.noise = self.pulse_height / 30.0
        self.tau_mu = 2197  # muyon life time in ns
        self.detector_efficiency = 0.95 if "prbInteraction" not in config_dict else\
            config_dict["prbInteraction"]
        self.stopping_probability = 0.10  if "prb2ndPulse" not in config_dict else\
            config_dict["prb2ndPulse"]

    def __call__(self, nchan):
        # initialize output array with noise signal
        pulse = np.float32(self.noise * (0.5 - np.random.rand(nchan, self.number_of_samples)))

        if np.random.rand() < self.stopping_probability:  # stopped muon ?
            stopped_mu = True
            n1 = min(2, nchan)  # only 2 layers for 1st pulse
        else:
            stopped_mu = False  # 4 layers for passing muon
            n1 = nchan

        # one pulse at trigger position in layers one and two
        for i_layer in range(n1):
            # random pulse height for trigger pulse
            pheight = self.pulse_height + self.pulse_spread * np.random.normal()
            if i_layer == 0:
                #  respect trigger condition in layer 1
                while pheight < self.trigger_level:
                    pheight = self.pulse_height + self.pulse_spread * np.random.normal()
            if np.random.rand() < self.detector_efficiency:
                pulse[i_layer, self.mn_position : self.mn_position + self.plen] += pheight * self.pulse_template

        # return if muon was not stopped
        if stopped_mu:
            # add delayed pulse(s)
            t_mu = -self.tau_mu * np.log(np.random.rand())  # muon life time
            pos2 = int(t_mu / self.sample_time_ns) + self.pre_trigger_samples
            if np.random.rand() > 0.5:  # upward decay electron
                for i_layer in range(0, min(nchan, 2)):
                    # random pulse height and position for 2nd pulse
                    ## pheight2 = np.random.rand()*maxheight
                    pheight2 = self.pulse_height + self.pulse_spread * np.random.normal()
                    if np.random.rand() < self.detector_efficiency and pos2 < self.mx_position:
                        pulse[i_layer, pos2 : pos2 + self.plen] += pheight2 * self.pulse_template
            else:
                for i_layer in range(min(nchan, 2), min(nchan, 4)):
                    # random pulse height and position for 2nd pulse
                    ## pheight2 = np.random.rand()*maxheight
                    pheight2 = self.pulse_height + self.pulse_spread * np.random.normal()
                    if np.random.rand() < self.detector_efficiency and pos2 < self.mx_position:
                        pulse[i_layer, pos2 : pos2 + self.plen] += pheight2 * self.pulse_template
        pulse += self.analogue_offset_mv  # apply analogue offset

        # simulate timing via sleep: respect wait time
        if self.random:  # random ...
            time.sleep(-self.sleeptime * np.log(np.random.rand()))  # random Poisson sleept time
        else:  # ... or fixed time
            time.sleep(self.sleeptime)  # fixed sleep time

        return pulse


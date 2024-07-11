#!/usr/bin/env python3
"""Script to generate input spectra for the signal generator of mcphy.py

The convention is to use 4096 channels for a range from 0 to 500 mV.
Pulseheights are drawn randomly from this spectrum, and pulses are formed
according to the frequency and the rise and fall times specified in
the graphical interface. The signals are available at the *out1*
connector of the RedPitaya board.

Pulses can be generated at a fixed frequency, or as random pulses
corresponding to a Poisson process.
"""

import numpy as np


len = 4096
s = np.zeros(len, dtype=int)

for i in range(16):
    s[(i + 1) * 250 - 1] = 1000

# s[4095]=1000

for i in range(len):
    print(s[i])

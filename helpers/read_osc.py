#!/usr/bin/env python3
"""Script to read and plot spectrum exported by mchpa.py"""

import sys
import numpy as np
import matplotlib.pyplot as plt

if len(sys.argv) == 2:
    filen = sys.argv[1]
else:
    filen = "5khz10mus.osc"

osc = np.fromfile(filen, dtype=np.int16)
osc1 = osc[0::2]
osc2 = osc[1::2]
print("number of  samples -  osc1: ", len(osc1), " osc2: ", len(osc2))

chan = [i + 0.5 for i in range(len(osc1))]
plt.plot(chan, osc1, "-", color="orange", lw=1)
plt.plot(chan, osc2, "-", color="lightblue", lw=1)
plt.xlabel("ADCcounts", size="x-large")
plt.ylabel("time bin", size="x-large")
plt.yscale("linear")
plt.show()

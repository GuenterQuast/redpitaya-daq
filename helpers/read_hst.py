#!/usr/bin/env python3
"""Script to read and plot spectrum exported by mchpa.py"""

import sys
import numpy as np
import matplotlib.pyplot as plt

if len(sys.argv) == 2:
    filen = sys.argv[1]
else:
    filen = "5khz10mus.hst"

hst = np.loadtxt(filen, dtype=np.uint32)
# print(len(hst), hst)

chan = [i + 0.5 for i in range(len(hst))]
plt.plot(chan, hst)
plt.xlabel("channel #", size="x-large")
plt.ylabel("counts", size="x-large")
plt.yscale("log")
plt.show()

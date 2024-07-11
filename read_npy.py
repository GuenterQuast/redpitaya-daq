#!/usr/bin/env python3
"""read file from redPoscdaq (in npy format) and display data"""

import numpy as np
import sys
import matplotlib.pyplot as plt

data = np.load(sys.argv[1], mmap_mode="r")
print("data read sucessfully, shape = ", data.shape)

n_samples = len(data[0, 0])
xplt = 0.5 + np.linspace(0, n_samples, num=n_samples, endpoint=True)
fig = plt.figure("Oscillogram", figsize=(8, 6))

for d in data:
    plt.plot(xplt, d[0], "-")
    plt.plot(xplt, d[1], "-")
    plt.xlabel("time bin")
    plt.ylabel("Voltage")
    plt.show()

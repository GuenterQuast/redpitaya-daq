#!/usr/bin/env python3
"""peakFitter: find and fit peaks in gamma spectrum

algorithm: perform a tow-stage determination of peak posisions:

  1. scipi.signal.find_peaks() is run on a smoothened histogram of channel counts.
  2. the characteristica of identified peaks are used as starting points for
     histogram fits with kafe2 based on the binned negative log-likelhood method.
"""

import argparse
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

#
from PhyPraKit import meanFilter
from kafe2 import HistFit, HistContainer, Plot


# define fit function
def gauss_plus_bkg(x, Ns=1000, mu=1000, sig=50.0, Nb=100.0, s=0.0, mn=0, mx=1.0):
    """Gaussian shape on linear background;"""
    # Ns: number of signal events
    # mu: peak posision
    # sig: peak width in sigma
    # Nb: mumber of background events in interval [mn, mx]
    # s: slope of base line
    # mn: lower bound of fit interval (as fixed parameter)
    # mx: upper bound of fit interval (as fixed parameter)

    # calculate integral of Gauss (not needed if Ns is total signal from -\inf to \inf)
    # I = norm.cdf(mx, mu, sig) - norm.cdf(mn, mu, sig)

    # Gaussian signal
    S = np.exp(-0.5 * ((x - mu) / sig) ** 2) / sig / np.sqrt(2 * np.pi)
    # linear background model
    B = (1 + (x - mu) * s) / (s / 2 * (mx**2 - mn**2) + (1 - s * mu) * (mx - mn))
    return Ns * S + Nb * B


# define command line arguments ...
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("filename", nargs="?", default="Co60.hst")
parser.add_argument(
    "-p", "--prominence", help="minimum peak height over baseline for scipy.find_peaks() (50)", type=float, default=50
)
parser.add_argument("-w", "--width", help="minimum peak width for scipy.find_peaks() (20)", type=float, default=20)
parser.add_argument(
    "-r",
    "--rel_height",
    help=" height at which full width is calculated in scipy.find_peaks() (0.5)",
    type=float,
    default=0.5,
)
parser.add_argument(
    "-f",
    "--fit_range_factor",
    help="fit_range_factor: fit range = fit_range_factor * fwhm (1.75)",
    type=float,
    default=1.75,
)
parser.add_argument(
    "-t", "--threshold", help="threshold, i.e. minimum valid channel nmber (51)", type=float, default=51
)
parser.add_argument("-s", "--smooth", help="smoothing-window size (5) ", type=float, default=5)
parser.add_argument("-n", "--noplot", action="store_true")
parser.add_argument("-k", "--kafe2_plots", action="store_true")
parser.add_argument("-v", "--verbose", action="store_true")
# ... and parse command line input
args = parser.parse_args()
filename = args.filename
# some constants for peak-finder
min_prominence = args.prominence  #  minimum peak hight over baseline
min_width = args.width  #  minimum width
rel_height = args.rel_height  #  width at half peak height (i.e. FWHM)
# constants for fit range
fit_range_factor = args.fit_range_factor  # fit range = fit_range_factor * fwhm
min_channel = args.threshold  # threshold for min. valid channel number
smoothing_window = args.smooth

verbose = args.verbose
plot = not args.noplot
kafe2_plots = args.kafe2_plots

# factor to convert Gaussian Sigma to full-width-half-maximum
sig2fwhm = 2.3548

# read data
hst = np.loadtxt(filename, dtype=np.uint32)
hlen = len(hst)
bin_edges = np.linspace(0, hlen, hlen + 1, endpoint=True)

# find maxima with scipy.signal.find_peaks()
#  firts, smoothen data to reduce statistical noise
if smoothing_window > 1:
    hst_s = meanFilter(hst, smoothing_window)
else:
    hst_s = hst
# search for peaks
peaks, peak_props = find_peaks(hst_s, prominence=min_prominence, width=min_width, rel_height=rel_height, wlen=350)
if verbose:
    print(len(peaks), "peaks found: ", peaks)
    print("prominences: ", peak_props["prominences"])
    print("left_bases: ", peak_props["left_bases"])
    print("right_bases: ", peak_props["right_bases"])
    print("fwhms: ", peak_props["widths"])

prominences = peak_props["prominences"]
left_bases = peak_props["left_bases"]
right_bases = peak_props["right_bases"]
fwhms = peak_props["widths"]

# fit for precise determination of peak properties and uncertainties
#   put data in kafe2 HistContainer
hdata = HistContainer(bin_edges=bin_edges, fill_data=hst)
hdata.label = "spectrum data"
# initialize arrays for output
fit_results = []
plot_ranges = np.zeros([len(peaks) + 1, 2])
plot_ranges2 = np.zeros([len(peaks) + 1, 2])
print("\n" + "*==* fit results:")
print("              mu   ±  d_mu  ( sig  sig/mu  FWHM/mu )")
# run fits for all identified peaks
for i, p in enumerate(peaks):
    wid = int(fit_range_factor * fwhms[i])
    base = (hst[left_bases[i]] + hst[right_bases[i]]) / 2.0
    mn = max(min_channel, int(p - wid))
    mx = int(p + wid)
    bins = range(mn, mx + 1)
    counts = hst[mn:mx]
    hfit_data = HistContainer(bin_edges=bins)
    hfit_data.label = "peak " + str(i + 1)
    hfit_data.set_bins(counts)
    # Fit
    fit = HistFit(data=hfit_data, model_function=gauss_plus_bkg, density=False)
    # !!! set initial values
    fit.set_parameter_values(mu=p, sig=wid, Nb=base * (mx - mn))
    fit.fix_parameter("mn", mn)
    fit.fix_parameter("mx", mx)
    # limit parameters to reasonable values
    fit.limit_parameter("sig", 0.0, None)
    fit.limit_parameter("Ns", 0.0, None)
    # fit.limit_parameter("Nb", 0., None) # biases uncertainty if at zero boundary
    # ? limit or fix slope of base line
    # fit.limit_parameter("s", -0.01, 0.01)
    # fit.fix_parameter("s", 0.)

    # perform fit
    fit.do_fit()
    if verbose:
        fit.report()  # optionally, report fit results

    # show and save results
    print(
        "{} peak@{}: {:.2f} ± {:.2g} ( {:.2f} {:.1f}%  {:.1f}% )".format(
            i + 1,
            p,
            fit.parameter_values[1],
            fit.parameter_errors[1],
            fit.parameter_values[2],
            100 * fit.parameter_values[2] / fit.parameter_values[1],
            100 * sig2fwhm * fit.parameter_values[2] / fit.parameter_values[1],
        )
    )
    fit_results = np.append(fit_results, fit)
    plot_ranges[i][0] = max(0, p - wid)
    plot_ranges[i][1] = min(hlen, p + wid + 1)
    plot_ranges2[i][0] = max(0, p - 2 * wid)
    plot_ranges2[i][1] = min(hlen, p + 2 * wid + 1)

# plot result
if plot:
    fig = plt.figure("Spectrum", figsize=(12, 10))
    fig.suptitle("Gamma spectrum " + filename)
    fig.subplots_adjust(left=0.12, bottom=0.1, right=0.95, top=0.95, wspace=None, hspace=0.1)
    ax0 = fig.add_subplot(211)
    ax1 = fig.add_subplot(212)
    ax0.set_ylabel("Entries per Channel")
    ax0.grid(linestyle="dotted", which="both")
    ax0.set_xticklabels([])
    ax1.set_ylabel("Entries per Channel")
    ax1.set_xlabel("Channel #")
    ax1.grid(linestyle="dotted", which="both")

    # show spectrum and result of find_peaks
    xhst = np.linspace(0, hlen, hlen, endpoint=False) + 0.5
    ax0.plot(xhst, hst_s, "b-", linewidth=1, zorder=2, label="smoothed channel counts")
    ax0.errorbar(
        xhst,
        hst,
        yerr=np.sqrt(hst),
        zorder=1,
        label="channel counts",
        fmt=".",
        color="grey",
        markersize=2,
        linewidth=2,
        alpha=0.5,
    )
    ax0.plot(peaks, hst_s[peaks], "x", color="red", markersize=10, zorder=3, label="result of find_peaks()")
    ax0.legend(loc="best")

    # show fitted peaks
    ax1.errorbar(xhst, hst, yerr=np.sqrt(hst), fmt=".", color="grey", alpha=0.25, zorder=1, label="channel counts")
    # select colors for peaks
    pcolors = (
        "steelblue",
        "darkorange",
        "green",
        "orchid",
        "turquoise",
        "tomato",
        "green",
        "pink",
        "salmon",
        "yellowgreen",
    )
    for i, fit in enumerate(fit_results):
        # plot fitted peak in fit range
        colr = pcolors[i % 10]
        xplt = np.linspace(plot_ranges[i][0], plot_ranges[i][1], 10 * int((plot_ranges[i][1] - plot_ranges[i][0])))
        ax1.plot(
            xplt,
            gauss_plus_bkg(xplt, *fit.parameter_values),
            linestyle="solid",
            linewidth=3,
            color=colr,
            zorder=2,
            label="peak " + str(i + 1) + "@" + str(int(10 * fit.parameter_values[1]) / 10.0),
        )
        # plot fitted peak near fit region
        xplt2 = np.linspace(plot_ranges2[i][0], plot_ranges2[i][1], 10 * int((plot_ranges[i][1] - plot_ranges[i][0])))
        ax1.plot(
            xplt2, gauss_plus_bkg(xplt2, *fit.parameter_values), zorder=2, linestyle="dotted", linewidth=2, color=colr
        )
        # show fitted peak properties
        mu = fit.parameter_values[1]
        sig = fit.parameter_values[2]
        fwhm = sig2fwhm * sig
        mx = gauss_plus_bkg(mu, *fit.parameter_values)
        h = fit.parameter_values[0] / np.sqrt(2 * np.pi) / sig
        ax1.vlines(mu, mx - h, mx, linewidth=3, color="goldenrod")
        ax1.vlines(mu, 0, mx - h, linewidth=1, linestyle="dashed", color="goldenrod")
        ax1.hlines(mx - h / 2, mu - fwhm / 2, mu + fwhm / 2, linewidth=2, color="goldenrod")
        ax1.hlines(mx - h, mu - fwhm / 4, mu + fwhm / 4, linewidth=3, color="goldenrod")
        ax1.legend(loc="best")

    if kafe2_plots:
        # kafe2 plots
        fit_results = np.append(fit_results, hdata)
        p = Plot(fit_results)
        p.customize("data", "alpha", [(i, 0.25) for i in range(len(peaks))] + [(len(peaks), 0.05)])
        p.plot()
    plt.show()

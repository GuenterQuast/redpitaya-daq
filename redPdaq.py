#!/usr/bin/env python3
"""redPoscdaq: fast data acquistion using the oscilloscope client of the MCPHA
application running on a RedPitaya FPGA board

Contains a button to run the oscilloscope in daq mode, i.e. it is restarted
continously. If defined, data is exported via calling a callback function.
Optionally, triggered waveforms can be stored a numpy binary file
(.npy format).

Code derived from mcpha.py by Pavel Demin

This code is compatible with release 20240204 of the alpine linux image
https://github.com/pavel-demin/red-pitaya-notes/releases/tag/20240204
"""

script_name = "redPdaq.py"

# Communication with server process is achieved via command codes:
#   command(code, number, data)  #    number typically is channel number
#
# code values
# code  2:  reset/initialze oscilloscope
# code  4:  set decimation factor
# code 11:  read status
# code 13:  set trigger source chan 1/2
# code 14:  set trigger slope rise/fall
# code 15:  set trigger mode norm/autoUi_HstDisplay, QWidget = loadUiType("mcpha_hst.ui")
# code 16:  set trigger level in ADC counts
# code 17:  set number of pre-trigger samples
# code 18:  set number of total samples
# code 19:  start oscilloscope
# code 20:  read oscilloscope data (two channels at once)
# code 21:  set pulse fall-time for generator in µs
# code 22:  set pulse rise-time in ns
# code 25:  set pulse rate in kHz
# code 26:  fixed frequency or poisson
# code 27_  reset generator
# code 28:  set bin for pulse distribution, as a histogram with 4096 channels, 0-500 mV
# code 29:  start generator
# code 30:  stop generator

import argparse
import os
import sys
import time
import struct
from pathlib import Path
import yaml

from functools import partial
import numpy as np
import matplotlib
from matplotlib.figure import Figure


# !!! for conditional import from npy_append_array !!!
def import_npy_append_array():
    global NpyAppendArray
    from npy_append_array import NpyAppendArray


from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt

if "PyQt5" in sys.modules:
    from PyQt5.uic import loadUiType
    from PyQt5.QtCore import Qt, QTimer, QEventLoop, QRegExp
    from PyQt5.QtGui import QPalette, QColor, QRegExpValidator
    from PyQt5.QtWidgets import QApplication, QMainWindow, QDialog, QFileDialog
    from PyQt5.QtWidgets import QWidget, QLabel, QCheckBox, QComboBox
    from PyQt5.QtNetwork import QAbstractSocket, QTcpSocket
else:
    from PySide2.QtUiTools import loadUiType
    from PySide2.QtCore import Qt, QTimer, QEventLoop, QRegExp
    from PySide2.QtGui import QPalette, QColor, QRegExpValidator
    from PySide2.QtWidgets import QApplication, QMainWindow, QDialog, QFileDialog
    from PySide2.QtWidgets import QWidget, QLabel, QCheckBox, QComboBox
    from PySide2.QtNetwork import QAbstractSocket, QTcpSocket

# define global graphics style
pref_style = "default"
_style = pref_style if pref_style in plt.style.available else "default"
plt.style.use(_style)

Ui_RPCONTROL, QMainWindow = loadUiType("rpControl.ui")
Ui_LogDisplay, QWidget = loadUiType("mcpha_log.ui")
Ui_HstDisplay, QWidget = loadUiType("mcpha_hst.ui")
Ui_OscDisplay, QWidget = loadUiType("mcpha_daq.ui")
Ui_GenDisplay, QWidget = loadUiType("mcpha_gen.ui")

if sys.platform != "win32":
    path = "."
else:
    path = os.path.expanduser("~")


class rpControl(QMainWindow, Ui_RPCONTROL):
    """control Pavel Demin's MCHPA application on RedPitaya

    Modes of operation:
       - in oscilloscope mode to just display data

       - in daq mode, i.e. read data at maximum rate,
           optionally recording data to disk or calling an external function
    """

    rates = {0: 1, 1: 4, 2: 8, 3: 16, 4: 32, 5: 64, 6: 128, 7: 256}

    def __init__(self, callback=None, conf_dict=None):
        """
        Args:

          callback: function receiving recorded waveforms
          conf_dict: a configuration dictionary
        """
        super(rpControl, self).__init__()

        plt.style.use("default")  # set graphics style

        self.callback_function = callback
        # initialize parameters
        self.confd = {} if conf_dict is None else conf_dict
        self.parse_confd()
        # get configuration from command line
        if os.path.split(sys.argv[0])[1] == script_name:
            self.interactive = True
            self.parse_args()
        else:
            self.interactive = False
        self.callback = True if callback is not None else False

        # set physical units (for axis labels)
        self.get_physical_units()
        # set-up and show main window
        self.setupUi(self)
        # initialize variables
        self.IOconnected = False
        self.idle = True
        self.hst_waiting = [False for i in range(2)]
        self.osc_ready = False
        self.osc_waiting = False
        self.hst_reset = 0
        self.state = 0
        self.status = np.zeros(9, np.uint32)
        self.timers = self.status[:4].view(np.uint64)
        # create tabs
        self.log = LogDisplay()
        if self.interactive:  # histogram function with disabled start button
            self.hst1 = HstDisplay(self, self.log, 0)
            self.hst1.startButton.setEnabled(False)
            self.hst2 = HstDisplay(self, self.log, 1)
            self.hst2.startButton.setEnabled(False)
        else:
            # no spectrum
            self.hst1 = None
            self.hst2 = None
            # smaller window
            self.setWindowTitle("RedPitaya DAQ")
            self.setGeometry(0, 0, 800, 650)
            self.log.print("runnning in DAQ mode")
        self.osc_daq = OscDAQ(self, self.log)
        self.osc_daq.startButton.setEnabled(False)
        self.osc_daq.startDAQButton.setEnabled(False)
        self.gen = GenDisplay(self, self.log)
        self.tabindex_log = self.tabWidget.addTab(self.log, "Messages")
        self.tabWidget.addTab(self.hst1, "Spectrum Channel 1")
        self.tabWidget.addTab(self.hst2, "Spectrum Channel 2")
        self.tabindex_osc = self.tabWidget.addTab(self.osc_daq, "Oscilloscope")
        self.tabindex_gen = self.tabWidget.addTab(self.gen, "Pulse generator")
        # configure controls
        self.connectButton.clicked.connect(self.startIO)
        self.neg1Check.toggled.connect(partial(self.set_negator, 0))
        self.neg2Check.toggled.connect(partial(self.set_negator, 1))
        self.rateValue.addItems(map(str, rpControl.rates.values()))
        self.rateValue.setEditable(True)
        self.rateValue.lineEdit().setReadOnly(True)
        self.rateValue.lineEdit().setAlignment(Qt.AlignRight)
        for i in range(self.rateValue.count()):
            self.rateValue.setItemData(i, Qt.AlignRight, Qt.TextAlignmentRole)
        self.rateValue.setCurrentIndex(1)
        self.rateValue.currentIndexChanged.connect(self.set_rate)
        rx = QRegExp(
            r"^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])|rp-[0-9A-Fa-f]{6}\.local$"
        )
        self.addrValue.setValidator(QRegExpValidator(rx, self.addrValue))
        # create TCP socket
        self.socket = QTcpSocket(self)
        self.socket.connected.connect(self.connected)
        self.socket.error.connect(self.display_error)
        # create event loop
        self.loop = QEventLoop()
        self.socket.readyRead.connect(self.loop.quit)
        self.socket.error.connect(self.loop.quit)
        # create timers
        self.startTimer = QTimer(self)  # timer for network connectin
        self.startTimer.timeout.connect(self.start_timeout)
        self.readTimer = QTimer(self)  # for readout
        # self.readTimer.timeout.connect(self.update_oscDisplay)
        self.readTimer.timeout.connect(self.read_timeout)

        # transfer command-line arguments to gui
        self.osc_daq.levelValue.setValue(self.trigger_level)
        self.osc_daq.autoButton.setChecked(self.trigger_mode)
        self.osc_daq.ch2Button.setChecked(self.trigger_source)
        self.osc_daq.fallingButton.setChecked(self.trigger_slope)
        self.rateValue.setCurrentIndex(self.decimation_index)
        self.neg1Check.setChecked(self.invert1)
        self.neg2Check.setChecked(self.invert2)

        # automatically connect and start
        if self.ip_address is not None:
            self.addrValue.setText(self.ip_address)
            self.log.print("starting IO")
            self.startIO()
        else:
            self.addrValue.setStyleSheet("color: darkorange")

    def parse_confd(self):
        # all relevant parameters are here
        #        self.ip_address ='192.168.1.100' if "ip_address" not in self.confd \
        self.ip_address = None if "ip_address" not in self.confd else self.confd["ip_address"]
        self.sample_size = 2048 if "number_of_samples" not in self.confd else self.confd["number_of_samples"]
        self.pretrigger_fraction = (
            0.05 if "pre_trigger_samples" not in self.confd else self.confd["pre_trigger_samples"] / self.sample_size
        )
        self.trigger_mode = (
            0
            if "trigger_mode" not in self.confd
            else 0
            if (self.confd["trigger_mode"] == "norm" or self.confd["trigger_mode"] == 0)
            else 1
        )
        self.trigger_source = 0 if "trigger_channel" not in self.confd else int(self.confd["trigger_channel"]) - 1
        self.trigger_level = 500 if "trigger_level" not in self.confd else self.confd["trigger_level"]
        self.trigger_slope = (
            0
            if "trigger_direction" not in self.confd
            else 0
            if (self.confd["trigger_direction"] == "rising" or self.confd["trigger_direction"] == "0")
            else 1
        )
        self.decimation_index = 1 if "decimation_index" not in self.confd else self.confd["decimation_index"]
        self.invert1 = 0 if "invert_channel1" not in self.confd else self.confd["invert_channel1"]
        self.invert2 = 0 if "invert_channel2" not in self.confd else self.confd["invert_channel2"]
        self.readInterval = 1000  # used to control update of oscilloscope display
        # other parameters
        self.filename = ""  # file name for data export, '' means disable
        self.autostart = False if "startDAQ" not in self.confd else self.confd["startDAQ"]

        # generator defaults
        self.gen_rateValue = 2000 if "genRate" not in self.confd else self.confd["genRate"]
        self.gen_poissonButton = True if "genPoisson" not in self.confd else self.confd["genPoisson"]
        self.gen_fallValue = 10 if "fallTime" not in self.confd else self.confd["fallTime"]
        self.gen_riseValue = 50 if "riseTime" not in self.confd else self.confd["riseTime"]
        self.gen_autostart = False if "genStart" not in self.confd else self.confd["genStart"]

    def parse_args(self):
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument(
            "-c", "--connect_ip", type=str, default=self.ip_address, help="connect IP address of RedPitaya"
        )
        # for oscilloscope display
        parser.add_argument(
            "-i", "--interval", type=int, default=self.readInterval, help="interval for readout (in ms)"
        )
        # trigger mode
        parser.add_argument(
            "-t", "--trigger_level", type=int, default=self.trigger_level, help="trigger level in ADC counts"
        )
        parser.add_argument(
            "--trigger_slope", type=int, choices={0, 1}, default=self.trigger_slope, help="trigger slope"
        )
        parser.add_argument(
            "--trigger_source", type=int, choices={1, 2}, default=self.trigger_source + 1, help="trigger channel"
        )
        parser.add_argument("--trigger_mode", type=int, choices={0, 1}, default=self.trigger_mode, help="trigger mode")
        parser.add_argument("-s", "--sample_size", type=int, default=self.sample_size, help="size of waveform sample")
        parser.add_argument(
            "-p", "--pretrigger_fraction", type=float, default=self.pretrigger_fraction, help="pretrigger fraction"
        )
        parser.add_argument("-f", "--file", type=str, default="", help="file name")
        args = parser.parse_args()
        # all relevant parameters are here
        self.ip_address = args.connect_ip
        self.sample_size = args.sample_size
        self.pretrigger_fraction = args.pretrigger_fraction
        self.readInterval = args.interval  # used to control oscilloscope display
        #
        self.trigger_level = args.trigger_level
        self.trigger_source = args.trigger_source - 1
        self.trigger_mode = args.trigger_mode
        self.trigger_slope = args.trigger_slope
        # other parameters
        self.filename = args.file
        if self.filename:
            # data recording with npy_append_array()
            import_npy_append_array()

    def get_physical_units(self):
        """get physical units corresponding to ADC units and channel numbers"""
        # Voltages: 4096 channels/Volt
        self.adc_unit = 1000 / 4096
        # time per sample at sampling rate of 125 MHz / decimation_factor
        self.time_bin = 0.008

    # !gq end

    def startIO(self):
        self.socket.connectToHost(self.addrValue.text(), 1001)  # connect to port 1001 (mcpha_server on RP)
        self.startTimer.start(1000)  # connection time-out
        self.connectButton.setText("Disconnect")
        self.connectButton.clicked.disconnect()
        self.connectButton.clicked.connect(self.stop)

    def stop(self):
        self.osc_daq.stop()
        self.gen.stop()
        self.readTimer.stop()
        self.startTimer.stop()
        self.loop.quit()
        self.socket.abort()
        self.connectButton.setText("Connect")
        self.connectButton.clicked.disconnect()
        self.connectButton.clicked.connect(self.startIO)
        self.addrValue.setStyleSheet("color: red")
        self.log.print("IO stopped")
        self.idle = True

    def closeEvent(self, event):
        self.stop()

    def start_timeout(self):
        self.log.print("error: connection timeout")
        self.stop()

    def display_error(self):
        self.log.print("error: %s" % self.socket.errorString())
        self.stop()

    def connected(self):
        # coming here when connection is established
        self.startTimer.stop()  # stop time-out
        self.IOconnected = True
        self.log.print("IO started")
        self.addrValue.setStyleSheet("color: green")
        self.tabWidget.setCurrentIndex(self.tabindex_osc)
        # enable all start buttons
        if self.hst1 is not None:
            self.hst1.startButton.setEnabled(True)
        if self.hst2 is not None:
            self.hst2.startButton.setEnabled(True)
        self.osc_daq.startButton.setEnabled(True)
        self.osc_daq.startDAQButton.setEnabled(True)

        # initialize variables for readout
        self.idle = False
        self.osc_waiting = False
        self.daq_waiting = False
        self.osc_reset = False
        self.osc_start = False
        self.state = 0
        self.hst_reset = 0
        self.hst_waiting = [False for i in range(2)]
        self.set_rate(self.rateValue.currentIndex())
        self.set_negator(0, self.neg1Check.isChecked())
        self.set_negator(1, self.neg2Check.isChecked())
        #
        # start timer calling update_oscData() read_timeout()
        self.readTimer.start(self.readInterval)

        #### start generator and oscilloscope in DAQ mode
        if self.gen_autostart:  # start pulse generator
            self.log.print("starting pulse generator")
            self.gen.start()
        if not self.interactive and self.autostart:  # start daq mode
            self.log.print("starting daq")
            self.osc_daq()  # __call__ method of osc_daq class

    def command(self, code, number, value):
        self.socket.write(struct.pack("<Q", code << 56 | number << 52 | (int(value) & 0xFFFFFFFFFFFFF)))

    def read_data(self, data):
        view = data.view(np.uint8)
        size = view.size
        while self.socket.state() == QAbstractSocket.ConnectedState and self.socket.bytesAvailable() < size:
            self.loop.exec_()
        if self.socket.bytesAvailable() < size:
            return False
        else:
            view[:] = np.frombuffer(self.socket.read(size), np.uint8)
            return True

    def read_timeout(self):
        """data transfer from RP,  triggered by QTimer readTimer"""
        # send reset commands for histograms
        if self.hst_reset & 1:
            self.command(0, 0, 0)  # hst 1
        if self.hst_reset & 2:
            self.command(0, 1, 0)  # hst 2
        if self.hst_reset & 4:
            self.command(1, 0, 0)  # reset timer 1
        if self.hst_reset & 8:
            self.command(1, 1, 0)  # reset timer 2
        self.hst_reset = 0
        if self.osc_reset:
            self.reset_osc()
        if self.osc_start:
            self.start_osc()
        # read histogram and oscilloscope data and update displays if not in daq mode
        if not self.daq_waiting:
            self.command(11, 0, 0)  # read status
            if not self.read_data(self.status):
                return
            # spectrum ch1
            if self.hst_waiting[0]:
                self.command(12, 0, 0)  # code 12: read histogram
                if self.read_data(self.hst1.buffer):
                    self.hst1.update(self.timers[0], False)
                else:
                    return
            # spectrum ch2
            if self.hst_waiting[1]:
                self.command(12, 1, 0)
                if self.read_data(self.hst2.buffer):
                    self.hst2.update(self.timers[1], False)
                else:
                    return
            # oscilloscope
            if self.osc_waiting and not self.status[8] & 1:
                self.command(20, 0, 0)  # read oscilloscope data
                if self.read_data(self.osc_daq.buffer):
                    self.osc_daq.update_osci_display()
                    self.mark_reset_osc()
                    self.mark_start_osc()
                else:
                    self.log.print("failed to read oscilloscope data")
                    return 1

    def run_oscDaq(self):
        """continuous fast data transfer from RedPitaya via mcpha oscilloscope"""
        # depends on
        #   self.start_daq()
        #   osc.process_data()

        # presently, not compatible with historgram mode, so pause
        if self.hst_waiting[0]:
            self.hst1.pause()
        if self.hst_waiting[1]:
            self.hst2.pause()
        # initialize trigger mode etc.
        self.osc_daq.start_daq()
        #
        self.reset_osc()
        self.start_osc()
        while self.daq_waiting:
            # check status
            self.read_status()
            if not self.read_data(self.status):
                self.log.print("failed to read status")
                return
            if not self.status[8] & 1:
                self.command(20, 0, 0)  # read oscilloscope data
                if self.read_data(self.osc_daq.buffer):
                    self.timestamp = time.time()
                    self.reset_osc()
                    self.osc_daq.process_data()
                    if self.callback:
                        self.callback_function(self.osc_daq.data)
                    self.start_osc()
                    self.osc_daq.deadT += time.time() - self.timestamp
                else:
                    self.log.print("failed to read oscilloscope data")
                    return

    def reset_hst(self, number):
        self.hst_reset |= 1 << number

    def reset_timer(self, number):
        self.hst_reset |= 4 << number

    def set_pha_delay(self, number, value):
        self.command(6, number, value)

    def set_pha_thresholds(self, number, min, max):
        self.command(7, number, min)
        self.command(8, number, max)

    def set_timer(self, number, value):
        self.command(9, number, value)

    def set_timer_mode(self, number, value):
        self.command(10, number, value)
        self.hst_waiting[number] = value

    def mark_start_osc(self):
        self.osc_start = True
        # self.osc_waiting = True

    def mark_reset_osc(self):
        self.osc_reset = True

    def reset_osc(self):
        self.command(2, 0, 0)
        self.osc_reset = False

    def start_osc(self):
        self.command(19, 0, 0)
        self.osc_start = False

    def read_status(self):
        self.command(11, 0, 0)

    def stop_osc(self):
        self.reset_osc()
        self.osc_waiting = False
        self.daq_waiting = False

    def set_rate(self, index):
        # set RP decimation factor
        self.command(4, 0, rpControl.rates[index])

    def set_negator(self, number, value):
        self.command(5, number, value)

    def set_trg_source(self, number):
        self.command(13, number, 0)

    def set_trg_slope(self, value):
        self.command(14, 0, value)

    def set_trg_mode(self, value):
        self.command(15, 0, value)

    def set_trg_level(self, value):
        self.command(16, 0, value)

    def set_osc_pre(self, value):
        self.command(17, 0, value)

    def set_osc_tot(self, value):
        self.command(18, 0, value)

    def set_gen_fall(self, value):
        self.command(21, 0, value)

    def set_gen_rise(self, value):
        self.command(22, 0, value)

    def set_gen_rate(self, value):
        self.command(25, 0, value)

    def set_gen_dist(self, value):
        self.command(26, 0, value)

    def reset_gen(self):
        self.command(27, 0)

    def set_gen_bin(self, value):
        self.command(28, 0, value)

    def start_gen(self):
        self.command(29, 0, 1)

    def stop_gen(self):
        self.command(30, 0, 0)


class LogDisplay(QWidget, Ui_LogDisplay):
    def __init__(self):
        super(LogDisplay, self).__init__()
        self.setupUi(self)

    def print(self, text):
        self.logViewer.appendPlainText(text)


class HstDisplay(QWidget, Ui_HstDisplay):
    def __init__(self, rpControl, log, number):
        super(HstDisplay, self).__init__()
        self.setupUi(self)
        # initialize variables
        self.rpControl = rpControl
        self.log = log
        self.number = number
        self.sum = 0
        self.time = np.uint64([75e8, 0])
        self.factor = 1
        self.bins = 4096
        self.min = 0
        self.max = self.bins - 1
        self.buffer = np.zeros(self.bins, np.uint32)
        if number == 0:
            self.color = "#FFAA00"
        else:
            self.color = "#00CCCC"
        # create figure
        self.figure = Figure()
        if sys.platform != "win32":
            self.figure.set_facecolor("none")
        # gq self.figure.subplots_adjust(left=0.18, bottom=0.08, right=0.98, top=0.95)
        self.figure.subplots_adjust(left=0.10, bottom=0.08, right=0.98, top=0.92)
        self.canvas = FigureCanvas(self.figure)
        self.plotLayout.addWidget(self.canvas)
        self.ax = self.figure.add_subplot(111)
        self.ax.grid()
        self.ax.set_ylabel("counts")
        self.xunit = "[{:.3f} mV / channel]".format(1000 / 4096 * self.factor)
        self.ax.set_xlabel("channel number " + self.xunit)
        #        self.ax.set_xlabel("channel number")
        # !gq
        self.ax_x2 = self.ax.secondary_xaxis("top", functions=(self.adc2mV, self.mV2adc))
        self.ax_x2.set_xlabel("Voltage [mV]", color="grey")
        # !gq end
        x = np.arange(self.bins)
        (self.curve,) = self.ax.plot(x, self.buffer, drawstyle="steps-mid", color=self.color)
        self.roi = [0, self.max]
        self.line = [None, None]
        self.active = [False, False]
        self.releaser = [None, None]
        # marker lines for roi
        self.line[0] = self.ax.axvline(self.min, picker=True, pickradius=5)
        self.line[1] = self.ax.axvline(self.max, picker=True, pickradius=5)
        # create navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, None, False)
        self.toolbar.layout().setSpacing(6)
        # remove subplots action
        actions = self.toolbar.actions()
        self.toolbar.removeAction(actions[6])
        self.toolbar.removeAction(actions[7])
        self.logCheck = QCheckBox("log scale")
        self.logCheck.setChecked(False)
        self.binsLabel = QLabel("rebin factor")
        self.binsValue = QComboBox()
        self.binsValue.addItems(["1", "2", "4", "8"])
        self.binsValue.setEditable(True)
        self.binsValue.lineEdit().setReadOnly(True)
        self.binsValue.lineEdit().setAlignment(Qt.AlignRight)
        for i in range(self.binsValue.count()):
            self.binsValue.setItemData(i, Qt.AlignRight, Qt.TextAlignmentRole)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.logCheck)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.binsLabel)
        self.toolbar.addWidget(self.binsValue)
        self.plotLayout.addWidget(self.toolbar)
        # configure controls
        actions[0].triggered.disconnect()
        actions[0].triggered.connect(self.home)
        self.logCheck.toggled.connect(self.set_scale)
        self.binsValue.currentIndexChanged.connect(self.set_bins)
        self.thrsCheck.toggled.connect(self.set_thresholds)
        self.startButton.clicked.connect(self.start)
        self.resetButton.clicked.connect(self.reset)
        self.saveButton.clicked.connect(self.save)
        self.loadButton.clicked.connect(self.load)
        self.canvas.mpl_connect("motion_notify_event", self.on_motion)
        self.canvas.mpl_connect("pick_event", self.on_pick)
        # update controls
        self.set_thresholds(self.thrsCheck.isChecked())
        self.set_time(self.time[0])
        self.set_scale(self.logCheck.isChecked())

    # !gq helper functions to convert adc counts to physical units
    def adc2mV(self, c):
        """convert adc-count to Voltage in mV"""
        return c * self.rpControl.adc_unit * self.factor

    def mV2adc(self, v):
        """convert voltage in mV to adc-count"""
        return v / (self.rpControl.adc_unit * self.factor)

    # !gq end helper

    def start(self):
        if self.rpControl.idle:
            return
        self.set_thresholds(self.thrsCheck.isChecked())
        self.set_enabled(False)
        h = self.hoursValue.value()
        m = self.minutesValue.value()
        s = self.secondsValue.value()
        value = (h * 3600000 + m * 60000 + s * 1000) * 125000
        self.sum = 0
        self.time[:] = [value, 0]
        self.rpControl.reset_timer(self.number)
        self.rpControl.set_pha_delay(self.number, 100)
        self.rpControl.set_pha_thresholds(self.number, self.min, self.max)
        self.rpControl.set_timer(self.number, value)
        #
        self.resume()

    def pause(self):
        self.rpControl.set_timer_mode(self.number, 0)
        self.startButton.setText("Resume")
        self.startButton.clicked.disconnect()
        self.startButton.clicked.connect(self.resume)
        self.log.print("timer %d stopped" % (self.number + 1))

    def resume(self):
        self.rpControl.set_timer_mode(self.number, 1)
        self.startButton.setText("Pause")
        self.startButton.clicked.disconnect()
        self.startButton.clicked.connect(self.pause)
        self.log.print("timer %d started" % (self.number + 1))

    def stop(self):
        self.rpControl.set_timer_mode(self.number, 0)
        self.set_enabled(True)
        self.set_time(self.time[0])
        self.startButton.setText("Start")
        self.startButton.clicked.disconnect()
        self.startButton.clicked.connect(self.start)
        self.log.print("timer %d stopped" % (self.number + 1))

    def reset(self):
        if self.rpControl.idle:
            return
        self.stop()
        self.rpControl.reset_hst(self.number)
        self.rpControl.reset_timer(self.number)
        self.totalValue.setText("%.2e" % 0)
        self.instValue.setText("%.2e" % 0)
        self.avgValue.setText("%.2e" % 0)
        self.buffer[:] = np.zeros(self.bins, np.uint32)
        self.update_plot()
        self.update_roi()

    def set_enabled(self, value):
        if value:
            self.set_thresholds(self.thrsCheck.isChecked())
        else:
            self.minValue.setEnabled(False)
            self.maxValue.setEnabled(False)
        self.thrsCheck.setEnabled(value)
        self.hoursValue.setEnabled(value)
        self.minutesValue.setEnabled(value)
        self.secondsValue.setEnabled(value)

    def home(self):
        self.set_scale(self.logCheck.isChecked())

    def set_xplot_range(self):
        """set x-range for histogram plot"""
        mn = self.min // self.factor
        mx = self.max // self.factor
        xsize = mx - mn
        self.ax.set_xlim(mn - 0.02 * xsize, mx * 1.02)
        self.ax.relim()
        self.ax.autoscale_view(scalex=True, scaley=True)

    def set_scale(self, checked):
        self.toolbar.home()
        self.toolbar.update()
        if checked:
            self.ax.set_ylim(1, 1e10)
            self.ax.set_yscale("log")
        else:
            self.ax.set_ylim(auto=True)
            self.ax.set_yscale("linear")
        # !gq size = self.bins // self.factor
        #    self.ax.set_xlim(-0.05 * size, size * 1.05)
        self.set_xplot_range()
        self.canvas.draw()

    def set_bins(self, value):
        factor = 1 << value
        self.factor = factor
        bins = self.bins // self.factor
        self.xunit = "[{:.3f} mV / channel]".format(1000 / 4096 * self.factor)
        self.ax.set_xlabel("channel number " + self.xunit)
        x = np.arange(bins)
        y = self.buffer.reshape(-1, self.factor).sum(-1)
        self.curve.set_xdata(x)
        self.curve.set_ydata(y)
        self.set_scale(self.logCheck.isChecked())
        # gq update roi
        self.roi[0] = self.min
        self.roi[1] = self.max
        self.update_roi()

    def set_thresholds(self, checked):
        self.minValue.setEnabled(checked)
        self.maxValue.setEnabled(checked)
        if checked:
            self.min = self.minValue.value()
            self.max = self.maxValue.value()
        else:
            self.min = 0
            self.max = self.bins - 1

        # !gq update xplot range and roi
        self.set_xplot_range()
        self.roi[0] = self.min
        self.roi[1] = self.max
        self.update_roi()

    def set_time(self, value):
        value = value // 125000
        h, mod = divmod(value, 3600000)
        m, mod = divmod(mod, 60000)
        s = mod / 1000
        self.hoursValue.setValue(int(h))
        self.minutesValue.setValue(int(m))
        self.secondsValue.setValue(s)

    def update(self, value, sync):
        self.update_rate(value)
        if not sync:
            self.update_time(value)
        self.update_plot()
        self.update_roi()

    def update_rate(self, value):
        sum = self.buffer.sum()
        self.totalValue.setText("%.2e" % sum)
        if value > self.time[1]:
            rate = (sum - self.sum) / (value - self.time[1]) * 125e6
            self.instValue.setText("%.2e" % rate)
        if value > 0:
            rate = sum / value * 125e6
            self.avgValue.setText("%.2e" % rate)
        self.sum = sum
        self.time[1] = value

    def update_time(self, value):
        if value < self.time[0]:
            self.set_time(self.time[0] - value)
        else:
            self.stop()

    def update_plot(self):
        y = self.buffer.reshape(-1, self.factor).sum(-1)
        self.curve.set_ydata(y)
        self.ax.relim()
        self.ax.autoscale_view(scalex=False, scaley=True)
        self.canvas.draw()

    def update_roi(self):
        y = self.buffer.reshape(-1, self.factor).sum(-1)
        x0 = self.roi[0] // self.factor
        x1 = self.roi[1] // self.factor
        roi = y[x0 : x1 + 1]
        y0 = roi[0]
        y1 = roi[-1]
        tot = roi.sum()
        bkg = (x1 + 1 - x0) * (y0 + y1) / 2.0
        self.roistartValue.setText("%d" % x0)
        self.roiendValue.setText("%d" % x1)
        self.roitotValue.setText("%.2e" % tot)
        self.roibkgValue.setText("%.2e" % bkg)
        self.line[0].set_xdata([x0, x0])
        self.line[1].set_xdata([x1, x1])
        self.canvas.draw_idle()

    def on_motion(self, event):
        if event.inaxes != self.ax:
            return
        x = int(event.xdata + 0.5)
        if x < 0:
            x = 0
        if x >= self.bins // self.factor:
            x = self.bins // self.factor - 1
        y = self.curve.get_ydata(True)[x]
        self.numberValue.setText("%d" % x)
        self.entriesValue.setText("%d" % y)
        delta = 40
        if self.active[0]:
            x0 = x * self.factor
            if x0 > self.roi[1] - delta:
                self.roi[0] = self.roi[1] - delta
            else:
                self.roi[0] = x0
            self.update_roi()
        if self.active[1]:
            x1 = x * self.factor
            if x1 < self.roi[0] + delta:
                self.roi[1] = self.roi[0] + delta
            else:
                self.roi[1] = x1
            self.update_roi()

    def on_pick(self, event):
        for i in range(2):
            if event.artist == self.line[i]:
                self.active[i] = True
                self.releaser[i] = self.canvas.mpl_connect("button_release_event", partial(self.on_release, i))

    def on_release(self, i, event):
        self.active[i] = False
        self.canvas.mpl_disconnect(self.releaser[i])

    def save(self):
        try:
            dialog = QFileDialog(self, "Save hst file", path, "*.hst")
            dialog.setDefaultSuffix("hst")
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            name = "histogram-%s.hst" % timestamp
            dialog.selectFile(name)
            dialog.setAcceptMode(QFileDialog.AcceptSave)
            if dialog.exec() == QDialog.Accepted:
                name = dialog.selectedFiles()
                np.savetxt(
                    name[0],
                    self.buffer,
                    fmt="%u",
                    header="mcpha spectrum " + timestamp + "\n counts per channel",
                    newline=os.linesep,
                )
                self.log.print("histogram %d saved to file %s" % ((self.number + 1), name[0]))
        except Exception as e:
            print(f"Exception: {e}")
            self.log.print("error: %s" % sys.exc_info()[1])

    def load(self):
        try:
            dialog = QFileDialog(self, "Load hst file", path, "*.hst")
            dialog.setDefaultSuffix("hst")
            dialog.setAcceptMode(QFileDialog.AcceptOpen)
            if dialog.exec() == QDialog.Accepted:
                name = dialog.selectedFiles()
                self.buffer[:] = np.loadtxt(name[0], np.uint32)
                self.update_plot()
        except Exception as e:
            print(f"Exception: {e}")
            self.log.print("error: %s" % sys.exc_info()[1])


class OscDAQ(QWidget, Ui_OscDisplay):
    """Oscilloscope display with daq mode:
    in daq_mode:
      - data is read from the RedPitaya at maximum rate
      - statistics is accumulated and displayed
      - optinally, data is output to a file or sent to an external function
    """

    def __init__(self, rpControl, log):
        super(OscDAQ, self).__init__()
        self.setupUi(self)
        # initialize variables
        self.rpControl = rpControl
        self.log = log
        self.l_tot = self.rpControl.sample_size
        self.pre = self.rpControl.pretrigger_fraction * self.l_tot
        self.buffer = np.zeros(self.l_tot * 2, np.int16)
        # same memory with different view of shape(2, samples_per_channel)
        self.data = self.buffer.reshape(2, self.l_tot, order="F")
        self.filename = rpControl.filename if self.rpControl.filename != "" else None
        # create figure
        self.figure = Figure()
        if sys.platform != "win32":
            self.figure.set_facecolor("none")
        # gq self.figure.subplots_adjust(left=0.18, bottom=0.08, right=0.98, top=0.95)
        self.figure.subplots_adjust(left=0.10, bottom=0.08, right=0.90, top=0.92)
        self.canvas = FigureCanvas(self.figure)
        self.plotLayout.addWidget(self.canvas)
        self.ax = self.figure.add_subplot(111)
        self.ax.grid()
        self.ax.set_xlim(-0.02 * self.l_tot, 1.02 * self.l_tot)
        self.ax.set_ylim(-4500, 4500)
        self.xunit = "[{:d} ns / sample]".format(4 * 8)
        self.ax.set_xlabel("sample number " + self.xunit)
        self.yunit = "[{:.3f} mV]".format(1.0 / 4.096)
        self.ax.set_ylabel("ADC units " + self.yunit)
        # self.ax.set_xlabel("sample number")
        # self.ax.set_ylabel("ADC units")
        # gq
        self.ax_x2 = self.ax.secondary_xaxis("top", functions=(self.tbin2t, self.t2tbin))
        self.ax_x2.set_xlabel("time [µs]", color="grey", size="x-large")
        self.ax_y2 = self.ax.secondary_yaxis("right", functions=(self.adc2mV, self.mV2adc))
        self.ax_y2.set_ylabel("Voltage [mV]", color="grey", size="x-large")
        # gq end
        self.osctxt = self.ax.text(0.1, 0.96, " ", transform=self.ax.transAxes, color="darkblue", alpha=0.7)

        x = np.arange(self.l_tot)
        (self.curve2,) = self.ax.plot(x, self.buffer[1::2], color="#00CCCC", label="chan 2")
        (self.curve1,) = self.ax.plot(x, self.buffer[0::2], color="#FFAA00", label="chan 1")
        self.ax.legend(handles=[self.curve1, self.curve2])
        self.line = [None, None]
        self.line[0] = self.ax.axvline(self.pre, linestyle="dotted")
        self.line[1] = self.ax.axhline(self.levelValue.value(), linestyle="dotted")
        self.canvas.draw()
        # create navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, None, False)
        self.toolbar.layout().setSpacing(6)
        # remove subplots action
        actions = self.toolbar.actions()
        self.toolbar.removeAction(actions[6])
        self.toolbar.removeAction(actions[7])
        # configure colors
        self.plotLayout.addWidget(self.toolbar)
        palette = QPalette(self.ch1Label.palette())
        palette.setColor(QPalette.Window, QColor("#FFAA00"))
        palette.setColor(QPalette.WindowText, QColor("black"))
        self.ch1Label.setAutoFillBackground(True)
        self.ch1Label.setPalette(palette)
        self.ch1Value.setAutoFillBackground(True)
        self.ch1Value.setPalette(palette)
        palette.setColor(QPalette.Window, QColor("#00CCCC"))
        palette.setColor(QPalette.WindowText, QColor("black"))
        self.ch2Label.setAutoFillBackground(True)
        self.ch2Label.setPalette(palette)
        self.ch2Value.setAutoFillBackground(True)
        self.ch2Value.setPalette(palette)
        # configure controls
        self.autoButton.toggled.connect(self.rpControl.set_trg_mode)
        self.ch2Button.toggled.connect(self.rpControl.set_trg_source)
        self.fallingButton.toggled.connect(self.rpControl.set_trg_slope)
        self.levelValue.valueChanged.connect(self.set_trg_level)
        self.startButton.clicked.connect(self.start)
        self.startDAQButton.clicked.connect(self.rpControl.run_oscDaq)
        self.saveButton.clicked.connect(self.save)
        self.loadButton.clicked.connect(self.load)
        self.canvas.mpl_connect("motion_notify_event", self.on_motion)

        self.rpControl.osc_ready = True

    def __call__(self):
        # run in data acquisition mode
        self.rpControl.run_oscDaq()

    # gq helper functions to convert acd channels and sampling time to physical units
    def tbin2t(self, tbin):
        """convert time bin to time in µs"""
        dfi = self.rpControl.rateValue.currentIndex()  # current decimation factor index
        df = 4 if dfi == -1 else rpControl.rates[dfi]  # decimation factor
        return (tbin - self.pre) * self.rpControl.time_bin * df

    def t2tbin(self, t):
        """convert time in µs to time bin"""
        dfi = self.rpControl.rateValue.currentIndex()  # current decimation factor index
        df = 4 if dfi == -1 else rpControl.rates[dfi]  # decimation factor
        return t / (self.rpControl.time_bin * df) + self.pre

    def adc2mV(self, c):
        """convert adc-count to Voltage in mV"""
        return c * self.rpControl.adc_unit

    def mV2adc(self, v):
        """convert voltage in mV to adc-count"""
        return v / self.rpControl.adc_unit

    # gq end

    def setup_trigger(self):
        # extract trigger parameters from gui and send to server
        self.trg_mode = int(self.autoButton.isChecked())
        self.trg_source = int(self.ch2Button.isChecked())
        self.trg_slope = int(self.fallingButton.isChecked())
        self.trg_level = self.levelValue.value()
        self.rpControl.set_trg_mode(self.trg_mode)
        self.rpControl.set_trg_source(self.trg_source)
        self.rpControl.set_trg_slope(self.trg_slope)
        self.rpControl.set_trg_level(self.trg_level)
        self.rpControl.set_osc_pre(self.pre)
        self.rpControl.set_osc_tot(self.l_tot)

    def set_gui4start(self):
        self.startButton.setText("Start monitor")
        self.startButton.setStyleSheet("")
        self.startButton.clicked.disconnect()
        self.startButton.clicked.connect(self.start)
        if self.rpControl.IOconnected:
            self.startDAQButton.setEnabled(True)
            if self.rpControl.hst1 is not None:
                self.rpControl.hst1.startButton.setEnabled(True)
            if self.rpControl.hst2 is not None:
                self.rpControl.hst2.startButton.setEnabled(True)

    def set_gui4stop(self):
        # set start and stop buttons
        self.startButton.setText("Stop")
        self.startButton.setStyleSheet("color: red")
        self.startButton.clicked.disconnect()
        self.startButton.clicked.connect(self.stop)
        self.startDAQButton.setEnabled(False)

    def get_actual_config(self):
        """update configuration dictionary with actual values from GUI
        """
        cd = {}
        cd["ip_address"]  = self.rpControl.addrValue.text()
        cd["number_of_samples"] = self.rpControl.sample_size
        cd["pre_trigger_samples"] = int(self.rpControl.pretrigger_fraction * self.rpControl.sample_size)
        cd["decimation_index"] = self.rpControl.rateValue.currentIndex()
        cd["invert_channel1"] = self.rpControl.neg1Check.isChecked()
        cd["invert_channel2"] = self.rpControl.neg2Check.isChecked()
        # actual trigger settings
        cd["trigger_mode"] = "auto" if self.trg_mode else "norm"        
        cd["trigger_channel"] = "2" if self.ch2Button.isChecked() else "1"
        cd["trigger_level"] = self.levelValue.value()
        cd["trigger_direction"] = "falling" if self.fallingButton.isChecked() else "rising"
        # generator defaults
        cd["genRate"] = self.rpControl.gen.rateValue.value()        
        cd["genPoisson"] = self.rpControl.gen.poissonButton.isChecked()
        cd["fallTime"] = self.rpControl.gen.fallValue.value()
        cd["riseTime"] = self.rpControl.gen.riseValue.value()
        return cd

        
    def save_config(self):
        """save configuration dictionary"""
        # check if directory prefix is in config file
        if "directory_prefix" in self.rpControl.confd:
            fname = self.rpControl.confd["directory_prefix"] + "redP_config.yaml"
            if os.path.isfile(fname):
                print(f"file {self.rpControl.confg['directory_prefix']} already existing")
            # Otherwise ask user for file name
        else:
            if self.filename is not None:
                p = Path(self.filename)
                nam = str(p.parent) + "/redP_config.yaml"
                fname, type = QFileDialog.getSaveFileName(self, "Save File", nam, "YAML files (*.yaml)")
                if fname == "":  # dont save if user cancels
                    return
        cd = self.get_actual_config()
        with open(fname, 'w') as f:
            f.write(yaml.dump(cd))
         
    def start(self):
        """start oscilloscope display"""
        if self.rpControl.idle:
            return
        #
        self.setup_trigger()
        self.set_gui4stop()
        #
        self.rpControl.mark_reset_osc()
        self.rpControl.mark_start_osc()
        self.rpControl.osc_waiting = True
        self.osctxt.set_text("")
        self.log.print("oscilloscope started")

    def start_daq(self):
        """start oscilloscope in daq mode"""
        if self.rpControl.idle:
            return
        # initialize daq statisics
        self.NTrig = 0
        self.dN = 0
        self.Nprev = self.NTrig
        self.T0 = time.time()
        self.deadT = 0.0
        self.Tprev = self.T0
        self.dT = 0.0
        # set-up trigger and GUI Buttons
        self.setup_trigger()
        self.set_gui4stop()
        # disable spectrum update
        if self.rpControl.hst1 is not None:
            self.rpControl.hst1.startButton.setEnabled(False)
        if self.rpControl.hst2 is not None:
            self.rpControl.hst2.startButton.setEnabled(False)
        self.rpControl.daq_waiting = True
        self.log.print("daq started")
        # save configuration
        self.save_config()

    def stop(self):
        self.rpControl.stop_osc()
        self.set_gui4start()
        self.log.print("oscilloscope stopped")

    def process_data(self):
        """statistics recorded data:

        - count number of Triggers and keep account of timing;
        - graphical display of a subset of the data
        """
        self.NTrig += 1
        t = time.time()
        dt = t - self.Tprev
        self.Tprev = t
        self.dT += dt
        # dead_time_fraction = self.deadT/dt
        self.deadT = 0.0
        #
        # do something with data (e.g. pass to sub-process via mpQueue)
        # write to file:
        if self.filename is not None:
            with NpyAppendArray(self.filename) as npa:
                npa.append(np.array([self.data]))
        #
        # output status and update scope display once per readInterval
        if 1000 * self.dT >= self.rpControl.readInterval:
            dN = self.NTrig - self.Nprev
            r = dN / self.dT
            self.Nprev = self.NTrig
            T_active = t - self.T0
            self.dT = 0.0
            status_txt = "active: {:.0f}s  trigger rate: {:.0f} Hz,  data rate: {:.3g} MB/s".format(
                T_active, r, r * self.l_tot * 4e-6
            )
            # print(status_txt, end='\r')
            self.osctxt.set_text(status_txt)
            # update graph on display
            self.curve1.set_ydata(self.data[0])
            self.curve2.set_ydata(self.data[1])
            self.xunit = "[{:d} ns / sample]".format(8 * rpControl.rates[self.rpControl.rateValue.currentIndex()])
            self.ax.set_xlabel("sample number " + self.xunit)
            self.canvas.draw()

    def update_osci_display(self):
        self.curve1.set_ydata(self.buffer[0::2])
        self.curve2.set_ydata(self.buffer[1::2])
        self.xunit = "[{:d} ns / sample]".format(8 * rpControl.rates[self.rpControl.rateValue.currentIndex()])
        self.ax.set_xlabel("sample number " + self.xunit)
        self.canvas.draw()

    def set_trg_level(self, value):
        self.line[1].set_ydata([value, value])
        self.canvas.draw()
        self.rpControl.set_trg_level(value)

    def on_motion(self, event):
        if event.inaxes != self.ax:
            return
        x = int(event.xdata + 0.5)
        if x < 0:
            x = 0
        if x >= self.l_tot:
            x = self.l_tot - 1
        y1 = self.curve1.get_ydata(True)[x]
        y2 = self.curve2.get_ydata(True)[x]
        self.timeValue.setText("%d" % x)
        self.ch1Value.setText("%d" % y1)
        self.ch2Value.setText("%d" % y2)

    def save(self):
        try:
            dialog = QFileDialog(self, "Save osc file", path, "*.osc")
            dialog.setDefaultSuffix("osc")
            name = "oscillogram-%s.osc" % time.strftime("%Y%m%d-%H%M%S")
            dialog.selectFile(name)
            dialog.setAcceptMode(QFileDialog.AcceptSave)
            if dialog.exec() == QDialog.Accepted:
                name = dialog.selectedFiles()
                self.buffer.tofile(name[0])
                self.log.print("histogram %d saved to file %s" % ((self.number + 1), name[0]))
        except Exception as e:
            print(f"Exception: {e}")
            self.log.print("error: %s" % sys.exc_info()[1])

    def load(self):
        try:
            dialog = QFileDialog(self, "Load osc file", path, "*.osc")
            dialog.setDefaultSuffix("osc")
            dialog.setAcceptMode(QFileDialog.AcceptOpen)
            if dialog.exec() == QDialog.Accepted:
                name = dialog.selectedFiles()
                self.buffer[:] = np.fromfile(name[0], np.int16)
                self.update()
        except Exception as e:
            print(f"Exception: {e}")
            self.log.print("error: %s" % sys.exc_info()[1])


class GenDisplay(QWidget, Ui_GenDisplay):
    def __init__(self, rpControl, log):
        super(GenDisplay, self).__init__()
        self.setupUi(self)
        # initialize variables
        self.rpControl = rpControl
        self.poissonButton.setChecked(self.rpControl.gen_poissonButton)
        self.fallValue.setValue(self.rpControl.gen_fallValue)
        self.riseValue.setValue(self.rpControl.gen_riseValue)
        self.rateValue.setValue(self.rpControl.gen_rateValue)
        self.log = log
        self.bins = 4096
        self.buffer = np.zeros(self.bins, np.uint32)
        for i in range(16):  # initialize with delta-functions
            self.buffer[(i + 1) * 256 - 1] = 1
        # create figure
        self.figure = Figure()
        if sys.platform != "win32":
            self.figure.set_facecolor("none")
        # !gq self.figure.subplots_adjust(left=0.18, bottom=0.08, right=0.98, top=0.95)
        self.figure.subplots_adjust(left=0.08, bottom=0.08, right=0.98, top=0.92)
        self.canvas = FigureCanvas(self.figure)
        self.plotLayout.addWidget(self.canvas)
        self.ax = self.figure.add_subplot(111)
        self.ax.grid()
        self.ax.set_ylabel("counts")
        self.xunit = "[0.122 mV /channel]"
        self.ax.set_xlabel("channel number " + self.xunit)
        # self.ax.set_xlabel("channel number")
        # !gq
        self.ax_x2 = self.ax.secondary_xaxis("top", functions=(self.adc2mV, self.mV2adc))
        self.ax_x2.set_xlabel("Voltage [mV]", color="grey")
        x = np.arange(self.bins)
        (self.curve,) = self.ax.plot(x, self.buffer, drawstyle="steps-mid", color="#FFAA00")
        # create navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, None, False)
        self.toolbar.layout().setSpacing(6)
        # remove subplots action
        actions = self.toolbar.actions()
        self.toolbar.removeAction(actions[6])
        self.toolbar.removeAction(actions[7])
        self.logCheck = QCheckBox("log scale")
        self.logCheck.setChecked(False)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.logCheck)
        self.plotLayout.addWidget(self.toolbar)
        # configure controls
        actions[0].triggered.disconnect()
        actions[0].triggered.connect(self.home)
        self.logCheck.toggled.connect(self.set_scale)
        self.startButton.clicked.connect(self.start)
        self.loadButton.clicked.connect(self.load)

    # gq
    def adc2mV(self, c):
        """convert adc-count to Voltage in mV
        !!! there is a factor of two betwenn channel definition here and in hstDisplay !
        """
        return c * self.rpControl.adc_unit / 2

    def mV2adc(self, v):
        """convert voltage in mV to adc-count"""
        return v * self.rpControl.adc_unit * 2

    # gq end

    def start(self):
        if self.rpControl.idle:
            return
        self.rpControl.set_gen_fall(self.fallValue.value())
        self.rpControl.set_gen_rise(self.riseValue.value())
        self.rpControl.set_gen_rate(self.rateValue.value())
        self.rpControl.set_gen_dist(self.poissonButton.isChecked())
        for value in np.arange(self.bins, dtype=np.uint64) << 32 | self.buffer:
            self.rpControl.set_gen_bin(value)
        self.rpControl.start_gen()
        self.startButton.setText("Stop")
        self.startButton.clicked.disconnect()
        self.startButton.clicked.connect(self.stop)
        self.log.print("generator started")

    def stop(self):
        self.rpControl.stop_gen()
        self.startButton.setText("Start")
        self.startButton.clicked.disconnect()
        self.startButton.clicked.connect(self.start)
        self.log.print("generator stopped")

    def home(self):
        self.set_scale(self.logCheck.isChecked())

    def set_scale(self, checked):
        self.toolbar.home()
        self.toolbar.update()
        if checked:
            self.ax.set_ylim(1, 1e10)
            self.ax.set_yscale("log")
        else:
            self.ax.set_ylim(auto=True)
            self.ax.set_yscale("linear")
        self.ax.relim()
        self.ax.autoscale_view(scalex=True, scaley=True)
        self.canvas.draw()

    def load(self):
        try:
            dialog = QFileDialog(self, "Load gen file", path, "*.gen")
            dialog.setDefaultSuffix("gen")
            dialog.setAcceptMode(QFileDialog.AcceptOpen)
            if dialog.exec() == QDialog.Accepted:
                name = dialog.selectedFiles()
                self.buffer[:] = np.loadtxt(name[0], np.uint32)
                self.curve.set_ydata(self.buffer)
                self.ax.relim()
                self.ax.autoscale_view(scalex=False, scaley=True)
                self.canvas.draw()
        except Exception as e:
            print(f"Exception: {e}")
            self.log.print("error: %s" % sys.exc_info()[1])


class redP_consumer:
    def __init__(self):
        self.NTrig = 0
        self.dN = 0
        self.Nprev = self.NTrig
        self.T0 = time.time()
        self.Tprev = self.T0
        self.dT = 0.0

    def data_sink(self, data):
        """function called by redPoscdaq
        this simple version calculates statistics only
        """
        self.databuffer = data
        # analyze data
        self.NTrig += 1
        t = time.time()
        dt = t - self.Tprev
        self.Tprev = t
        self.dT += dt
        l_tot = len(self.databuffer[0])

        # output status and update scope display once per second
        if self.dT >= 1.0:
            dN = self.NTrig - self.Nprev
            r = dN / self.dT
            self.Nprev = self.NTrig
            T_active = t - self.T0
            self.dT = 0.0
            status_txt = "active: {:.1f}s  trigger rate: {:.2f} Hz,  data rate: {:.4g} MB/s".format(
                T_active, r, r * l_tot * 4e-6
            )
            print(status_txt, end="\r")


def run_rpControl(callback=None, conf_dict=None):
    # start redPidaya GUI under Qt5
    app = QApplication(sys.argv)
    dpi = app.primaryScreen().logicalDotsPerInch()
    matplotlib.rcParams["figure.dpi"] = dpi
    application = rpControl(callback=callback, conf_dict=conf_dict)
    application.show()
    sys.exit(app.exec_())


if __name__ == "__main__":  # --------------------------------------------
    #    run_rpControl()

    data_processor = redP_consumer()
    run_rpControl(callback=data_processor.data_sink)

import argparse
import tkinter as tk
import logging
import datetime
from threading import Thread

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib
import nidaqmx
import h5py

import qt3utils.nidaq
import qt3utils.datagenerators as datasources
import qt3utils.pulsers.pulseblaster
import nipiezojenapy

matplotlib.use('Agg')


parser = argparse.ArgumentParser(description='NI DAQ (PCIx 6363) / Jena Piezo Scanner',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('-d', '--daq-name', default = 'Dev1', type=str, metavar = 'daq_name',
                    help='NI DAQ Device Name')
parser.add_argument('-st', '--signal-terminal', metavar = 'terminal', default = 'PFI0', type=str,
                    help='NI DAQ terminal connected to input digital TTL signal')
parser.add_argument('-c', '--clock-rate', metavar = 'rate (Hz)', default = 100000, type=int,
                    help='''Specifies the clock rate in Hz. If using an external clock,
                    you should specifiy the clock rate here so that the correct counts per
                    second are displayed. If using the internal NI DAQ clock (default behavior),
                    this value specifies the clock rate to use. Per the NI DAQ manual,
                    use a suitable clock rate for the device for best performance, which is an integer
                    multiple downsample of the digital sample clock.''')
parser.add_argument('-n', '--num-data-samples-per-batch', metavar = 'N', default = 250, type=int,
                    help='''Number of data points to acquire per DAQ batch request.
                           Note that only ONE data point is shown in the scope.
                           After each request to the NI DAQ for data, the mean count
                           rate from the batch is computed and displayed. Increasing
                           the "num-data-samples-per-batch" should reduce your noise, but
                           slow the response of the scope. Increase this value if the
                           scope appears too noisy.''')
parser.add_argument('-ct', '--clock-terminal', metavar = 'terminal', default = None, type=str,
                    help='''Specifies the digital input terminal to the NI DAQ to use for a clock.
                            If None, which is the default, the internal NI DAQ clock is used.''')
parser.add_argument('-to', '--rwtimeout', metavar = 'seconds', default = 10, type=int,
                    help='NI DAQ read/write timeout in seconds.')
parser.add_argument('-sc', '--signal-counter', metavar = 'ctrN', default = 'ctr2', type=str,
                    help='NI DAQ interal counter (ctr1, ctr2, ctr3, ctr4)')
parser.add_argument('--piezo-write-channels', metavar = '<ch0,ch1,ch2>', default = 'ao0,ao1,ao2', type=str,
                    help='List of analog output channels used to control the piezo position')
parser.add_argument('--piezo-read-channels', metavar = '<ch0,ch1,ch2>', default = 'ai0,ai1,ai2', type=str,
                    help='List of analog input channels used to read the piezo position')
parser.add_argument('-r', '--randomtest', action = 'store_true',
                    help='When true, program will run showing random numbers. This is for development testing.')
parser.add_argument('-q', '--quiet', action = 'store_true',
                    help='When true,logger level will be set to warning. Otherwise, set to "info".')
parser.add_argument('-cmap', metavar = '<MPL color>', default = 'gray',
                    help='Set the MatplotLib colormap scale')
parser.add_argument('-pb', '--pulse-blaster', metavar = '<PB board number>', default = 0, type=int,
                    help='Pulse Blaster board number')

args = parser.parse_args()

logger = logging.getLogger(__name__)
logging.basicConfig()

if args.quiet is False:
    logger.setLevel(logging.INFO)



class ScanImage:
    def __init__(self, mplcolormap = 'gray'):
        self.fig, self.ax = plt.subplots()
        self.cbar = None
        self.cmap = mplcolormap
        self.cid = self.fig.canvas.mpl_connect('button_press_event', self.onclick)
        self.ax.set_xlabel('x position (um)')
        self.ax.set_ylabel('y position (um)')
        self.log_data = False

    def update(self, model):

        if self.log_data:
            data = np.log10(model.scanned_count_rate)
            data[np.isinf(data)] = 0 #protect against +-inf
        else:
            data = model.scanned_count_rate

        self.artist = self.ax.imshow(data, cmap=self.cmap, extent=[model.xmin,
                                                                   model.xmax + model.step_size,
                                                                   model.current_y + model.step_size,
                                                                   model.ymin])
        if self.cbar is None:
            self.cbar = self.fig.colorbar(self.artist, ax=self.ax)
        else:
            self.cbar.update_normal(self.artist)

        if self.log_data is False:
            self.cbar.formatter.set_powerlimits((0, 3))

        self.ax.set_xlabel('x position (um)')
        self.ax.set_ylabel('y position (um)')

    def reset(self):
        self.ax.cla()

    def set_onclick_callback(self, f):
        self.onclick_callback = f

    def onclick(self, event):
        if event.inaxes is self.ax:
            #todo: draw a circle around clicked point? Maybe with a high alpha, so that its faint
            self.onclick_callback(event)

class SidePanel():
    def __init__(self, root, scan_range):
        frame = tk.Frame(root)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        row = 0
        bold_font = ('Helvetica', 16, 'bold')
        tk.Label(frame, text="Scan Settings", font=bold_font).grid(row=row, column=1, pady=10)
        row += 1
        tk.Label(frame, text="x range (um)").grid(row=row, column=0)
        self.x_min_entry = tk.Entry(frame, width=10)
        self.x_max_entry = tk.Entry(frame, width=10)
        self.x_min_entry.insert(10, scan_range[0])
        self.x_max_entry.insert(10, scan_range[1])
        self.x_min_entry.grid(row=row, column=1)
        self.x_max_entry.grid(row=row, column=2)

        row += 1
        tk.Label(frame, text="y range (um)").grid(row=row, column=0)
        self.y_min_entry = tk.Entry(frame, width=10)
        self.y_max_entry = tk.Entry(frame, width=10)
        self.y_min_entry.insert(10, scan_range[0])
        self.y_max_entry.insert(10, scan_range[1])
        self.y_min_entry.grid(row=row, column=1)
        self.y_max_entry.grid(row=row, column=2)

        row += 1
        tk.Label(frame, text="step size (um)").grid(row=row, column=0)
        self.step_size_entry = tk.Entry(frame, width=10)
        self.step_size_entry.insert(10, 1.0)
        self.step_size_entry.grid(row=row, column=1)


        row += 1
        tk.Label(frame, text="set z (um)").grid(row=row, column=0)
        self.z_entry_text = tk.DoubleVar()
        self.z_entry = tk.Entry(frame, width=10, textvariable=self.z_entry_text)
        self.z_entry.grid(row=row, column=1)
        self.go_to_z_button = tk.Button(frame, text="Go To Z")
        self.go_to_z_button.grid(row=row, column=2)

        row += 1
        self.startButton = tk.Button(frame, text="Start Scan")
        self.startButton.grid(row=row, column=0)
        self.stopButton = tk.Button(frame, text="Stop Scan")
        self.stopButton.grid(row=row, column=1)
        self.saveScanButton = tk.Button(frame, text="Save Scan")
        self.saveScanButton.grid(row=row, column=2)

        row += 1
        self.popOutScanButton = tk.Button(frame, text="Popout Scan")
        self.popOutScanButton.grid(row=row, column=0)

        row += 1
        tk.Label(frame, text="Position").grid(row=row, column=0, pady=10)

        self.go_to_x_position_text = tk.DoubleVar()
        self.go_to_y_position_text = tk.DoubleVar()

        tk.Entry(frame, textvariable=self.go_to_x_position_text, width=7).grid(row=row, column=1, pady=5)
        tk.Entry(frame, textvariable=self.go_to_y_position_text, width=7).grid(row=row, column=2, pady=5)

        row += 1
        self.gotoButton = tk.Button(frame, text="Go To Position")
        self.gotoButton.grid(row=row, column=2)

        # row += 1
        # tk.Label(frame, text="Optimize Pos", font='Helvetica 16').grid(row=row, column=0, pady=10)
        row += 1
        tk.Label(frame, text="Optimize Range (um)").grid(row=row, column=0, columnspan=2)
        self.optimize_range_entry = tk.Entry(frame, width=10)
        self.optimize_range_entry.insert(5, 2)
        self.optimize_range_entry.grid(row=row, column=2)
        row += 1
        tk.Label(frame, text="Optimize StepSize (um)").grid(row=row, column=0, columnspan=2)
        self.optimize_step_size_entry = tk.Entry(frame, width=10)
        self.optimize_step_size_entry.insert(5, 0.25)
        self.optimize_step_size_entry.grid(row=row, column=2)
        row += 1
        self.optimize_x_button = tk.Button(frame, text="Optimize X")
        self.optimize_x_button.grid(row=row, column=0)
        self.optimize_y_button = tk.Button(frame, text="Optimize Y")
        self.optimize_y_button.grid(row=row, column=1)
        self.optimize_z_button = tk.Button(frame, text="Optimize Z")
        self.optimize_z_button.grid(row=row, column=2)
        
        row += 1
        bold_font = ('Helvetica', 16, 'bold')
        tk.Label(frame, text="Spectrometer Settings", font=bold_font).grid(row=row, column=1, pady=15)
        
        row += 1
        tk.Label(frame, text="Exposure Time (s)").grid(row=row, column=0)
        self.expose_time_entry = tk.Entry(frame, width=10)
        self.expose_time_entry.insert(10, self.spectrometer_settings.expose_time)
        self.expose_time_entry.grid(row=row, column=1)
        
        row += 1
        tk.Label(frame, text="Frames to Save").grid(row=row, column=0)
        self.spec_frames_entry = tk.Entry(frame, width=10)
        self.spec_frames_entry.insert(10, self.spectrometer_settings.spec_frames)
        self.spec_frames_entry.grid(row=row, column=1)
        
        row += 1
        tk.Label(frame, text="Center Wavelength (nm)").grid(row=row, column=0)
        self.center_wlength_entry = tk.Entry(frame, width=10)
        self.center_wlength_entry.insert(10, self.spectrometer_settings.center_wlength)
        self.center_wlength_entry.grid(row=row, column=1)
        
        row += 1
        tk.Label(frame, text="Spectral Range (nm)").grid(row=row, column=0)
        self.min_wavelength_entry = tk.Entry(frame, width=10)
        self.max_wavelength_entry = tk.Entry(frame, width=10)
        self.min_wavelength_entry.insert(10, self.spectrometer_settings.min_wavelength)
        self.max_wavelength_entry.insert(10, self.spectrometer_settings.max_wavelength)
        self.min_wavelength_entry.grid(row=row, column=1)
        self.max_wavelength_entry.grid(row=row, column=2)
        
        row += 1
        bold_font = ('Helvetica', 16, 'bold')
        tk.Label(frame, text="Confocal View Settings", font=bold_font, underline=0).grid(row=row, column=1, pady=15)
        row += 1
        self.set_color_map_button = tk.Button(frame, text="Set Color")
        self.set_color_map_button.grid(row=row, column=0, pady=(2,15))
        self.mpl_color_map_entry = tk.Entry(frame, width=10)
        self.mpl_color_map_entry.insert(10, args.cmap)
        self.mpl_color_map_entry.grid(row=row, column=1, pady=(2,15))

        self.log10Button = tk.Button(frame, text="Log10")
        self.log10Button.grid(row=row, column=2, pady=(2,15))
import argparse
import tkinter as tk
import logging
from threading import Thread

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib
import nidaqmx

import qt3utils.datagenerators as datasources

matplotlib.use('Agg')


parser = argparse.ArgumentParser(description='NI DAQ (PCIx 6363) / PLE Scanner',
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
parser.add_argument('--piezo-write-channel', metavar = '<ch0>', default = 'ao0', type=str,
                    help='Analog output channel used to control the wavelength of the laser')
parser.add_argument('-r', '--randomtest', action = 'store_true',
                    help='When true, program will run showing random numbers. This is for development testing.')
parser.add_argument('-q', '--quiet', action = 'store_true',
                    help='When true,logger level will be set to warning. Otherwise, set to "info".')
parser.add_argument('-cmap', metavar = '<MPL color>', default = 'gray',
                    help='Set the MatplotLib colormap scale')

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
        self.ax.set_xlabel('Voltage')
        self.log_data = False


    def onclick(self, event):
        pass

class SidePanel():
    def __init__(self, root, scan_range):
        frame = tk.Frame(root)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        row = 0
        tk.Label(frame, text="Scan Settings", font='Helvetica 16').grid(row=row, column=0,pady=10)
        row += 1
        tk.Label(frame, text="x range (um)").grid(row=row, column=0)
        self.x_min_entry = tk.Entry(frame, width=10)
        self.x_max_entry = tk.Entry(frame, width=10)
        self.x_min_entry.insert(10, scan_range[0])
        self.x_max_entry.insert(10, scan_range[1])
        self.x_min_entry.grid(row=row, column=1)
        self.x_max_entry.grid(row=row, column=2)
        self.startButton = tk.Button(frame, text="Start Scan")
        self.startButton.grid(row=row, column=0)

class MainApplicationView():
    def __init__(self, main_frame, scan_range = [0,80]):
        frame = tk.Frame(main_frame)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scan_view = ScanImage(args.cmap)
        self.sidepanel = SidePanel(main_frame, scan_range)

        self.canvas = FigureCanvasTkAgg(self.scan_view.fig, master=frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(self.canvas, frame)
        toolbar.update()
        self.canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.canvas.draw()

class MainTkApplication():

    def __init__(self):
        self.root = tk.Tk()
        self.view = MainApplicationView(self.root)
        self.view.sidepanel.startButton.bind("<Button>", self.start_scan)

    #TODO: add device/channel name, change functionality to nidaq, add sweep loop and sleep() with settling time
    def start_scan(self, event = None):
        self.view.sidepanel.startButton['state'] = 'disabled'
        xmin = float(self.view.sidepanel.x_min_entry.get())
        xmax = float(self.view.sidepanel.x_max_entry.get())
        with nidaqmx.Task() as task:
            task.ao_channels.add_ao_voltage_chan("Dev1/ai0")
            task.write(xmin)

    def run(self):
        self.root.title("QT3PLE: Run PLE scan")
        self.root.deiconify()
        self.root.mainloop()

def main():
    tkapp = MainTkApplication()
    tkapp.run()


if __name__ == '__main__':
    main()

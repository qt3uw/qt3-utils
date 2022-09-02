import time
import argparse
import collections
import tkinter as tk
import tkinter.ttk as ttk
import logging
from threading import Thread

import numpy as np
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib
matplotlib.use('Agg')
import nidaqmx

import qt3utils.nidaq
import qt3utils.datagenerators as datasources
import nipiezojenapy

logger = logging.getLogger(__name__)

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
parser.add_argument('-n', '--num-data-samples-per-batch', metavar = 'N', default = 100, type=int,
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
parser.add_argument('-cmap', metavar = '<MPL color>', default = 'Reds',
                    help='Set the MatplotLib colormap scale')
args = parser.parse_args()


class ScanImage:
    def __init__(self, mplcolormap = 'Reds'):
        self.fig, self.ax = plt.subplots()
        self.cbar = None
        self.cmap = mplcolormap
        self.cid = self.fig.canvas.mpl_connect('button_press_event', self.onclick)
        self.ax.set_xlabel('x position (um)')
        self.ax.set_ylabel('y position (um)')
        self.log_data = False

    def update(self, model):

        if self.log_data:
            data = np.log10(model.data)
        else:
            data = model.data

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
            self.onclick_callback(event)

class SidePanel():
    def __init__(self, root):
        frame = tk.Frame(root)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)


        tk.Label(frame, text="x range (um)").grid(row=0, column=0)
        self.x_min_entry = tk.Entry(frame, width=10)
        self.x_max_entry = tk.Entry(frame, width=10)
        self.x_min_entry.insert(10, 0.01)
        self.x_max_entry.insert(10, 40.01)
        self.x_min_entry.grid(row=0, column=1)
        self.x_max_entry.grid(row=0, column=2)

        tk.Label(frame, text="y range (um)").grid(row=1, column=0)
        self.y_min_entry = tk.Entry(frame, width=10)
        self.y_max_entry = tk.Entry(frame, width=10)
        self.y_min_entry.insert(10, 0.01)
        self.y_max_entry.insert(10, 40.01)
        self.y_min_entry.grid(row=1, column=1)
        self.y_max_entry.grid(row=1, column=2)

        tk.Label(frame, text="y range (um)").grid(row=1, column=0)
        self.y_min_entry = tk.Entry(frame, width=10)
        self.y_max_entry = tk.Entry(frame, width=10)
        self.y_min_entry.insert(10, 0.01)
        self.y_max_entry.insert(10, 40.01)
        self.y_min_entry.grid(row=1, column=1)
        self.y_max_entry.grid(row=1, column=2)

        tk.Label(frame, text="step size (um)").grid(row=2, column=0)
        self.step_size_entry = tk.Entry(frame, width=10)
        self.step_size_entry.insert(10, 1.0)
        self.step_size_entry.grid(row=2, column=1)

        tk.Label(frame, text="N samples/step").grid(row=3, column=0)
        self.n_sample_size_entry = tk.Entry(frame, width=10)
        self.n_sample_size_entry.insert(50, 10)
        self.n_sample_size_entry.grid(row=3, column=1)

        tk.Label(frame, text="set z (um)").grid(row=4, column=0)
        self.z_entry = tk.Entry(frame, width=10)
        self.z_entry.grid(row=4, column=1)
        self.go_to_z_button = tk.Button(frame, text="Go To Z")
        self.go_to_z_button.grid(row=4, column=2)

        self.startButton = tk.Button(frame, text="Start")
        self.startButton.grid(row=5, column=0)
        self.stopButton = tk.Button(frame, text="Stop")
        self.stopButton.grid(row=5, column=1)
        self.log10Button = tk.Button(frame, text="Log10")
        self.log10Button.grid(row=5, column=2)

        tk.Label(frame, text="Selected Position (um)").grid(row=6, column=0, pady=5)

        self.go_to_x_position_text = tk.StringVar()
        self.go_to_x_position_text.set("x: ")
        self.go_to_y_position_text = tk.StringVar()
        self.go_to_y_position_text.set("y: ")
        self.clicked_x = None
        self.clicked_x = None

        tk.Label(frame, textvariable=self.go_to_x_position_text).grid(row=6, column=1, pady=5)
        tk.Label(frame, textvariable=self.go_to_y_position_text).grid(row=6, column=2, pady=5)

        self.gotoButton = tk.Button(frame, text="Go To Position")
        self.gotoButton.grid(row=7, column=2)

    def mpl_onclick_callback(self, mpl_event):
        if mpl_event.xdata and mpl_event.ydata:
            self.go_to_x_position_text.set(f'x: {mpl_event.xdata:.2f}')
            self.go_to_y_position_text.set(f'y: {mpl_event.ydata:.2f}')
            self.clicked_x = mpl_event.xdata
            self.clicked_y = mpl_event.ydata

class MainApplicationView():
    def __init__(self, master):
        frame = tk.Frame(master)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scan_view = ScanImage(args.cmap)
        self.sidepanel = SidePanel(master)
        self.scan_view.set_onclick_callback(self.sidepanel.mpl_onclick_callback)

        self.canvas = FigureCanvasTkAgg(self.scan_view.fig, master=frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(self.canvas, frame)
        toolbar.update()
        self.canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.canvas.draw()

class MainTkApplication():

    def __init__(self, data_model):
        self.root = tk.Tk()
        self.model = data_model

        self.view = MainApplicationView(self.root)
        self.view.sidepanel.startButton.bind("<Button>", self.start_scan)
        self.view.sidepanel.stopButton.bind("<Button>", self.stop_scan)
        self.view.sidepanel.log10Button.bind("<Button>", self.log_scan_image)
        self.view.sidepanel.gotoButton.bind("<Button>", self.go_to_position)
        self.view.sidepanel.go_to_z_button.bind("<Button>", self.go_to_z_button)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.scan_thread = None

        if self.model.controller:
            current_z = self.model.controller.get_current_position()[2]
        else:
            current_z = 20
        self.view.sidepanel.z_entry.insert(5, current_z)

    def run(self):
        self.root.title("Confocal Scanner")
        self.root.deiconify()
        self.root.mainloop()

    def go_to_position(self, event = None):
        if self.model.controller:
            self.model.controller.go_to_position(x = self.view.sidepanel.clicked_x, y = self.view.sidepanel.clicked_y)
        else:
            print(f'controller would have moved to x,y = {self.view.sidepanel.clicked_x:.2f}, {self.view.sidepanel.clicked_y:.2f}')

    def go_to_z_button(self, event = None):
        if self.model.controller:
            self.model.controller.go_to_position(z = float(self.view.sidepanel.z_entry.get()))
        else:
            print(f'controller would have moved to z = {float(self.view.sidepanel.z_entry.get()):.2f}')

    def log_scan_image(self, event = None):
        self.view.scan_view.log_data = not self.view.scan_view.log_data
        if len(self.model.data) > 0:
            self.view.scan_view.update(self.model)
            self.view.canvas.draw()

    def stop_scan(self, event = None):
        self.model.stop()
        self.view.sidepanel.startButton['state'] = 'normal'
        self.view.sidepanel.go_to_z_button['state'] = 'normal'
        self.view.sidepanel.gotoButton['state'] = 'normal'

    def scan_thread_function(self):

        while self.model.still_scanning():
            self.model.scan_x()
            self.view.scan_view.update(self.model)
            self.view.canvas.draw()
            self.model.move_y()

        self.view.sidepanel.startButton['state'] = 'normal'
        self.view.sidepanel.go_to_z_button['state'] = 'normal'
        self.view.sidepanel.gotoButton['state'] = 'normal'

    def start_scan(self, event = None):
        self.view.sidepanel.startButton['state'] = 'disabled'
        self.view.sidepanel.go_to_z_button['state'] = 'disabled'
        self.view.sidepanel.gotoButton['state'] = 'disabled'

        #clear the figure
        self.view.scan_view.reset()

        xmin = float(self.view.sidepanel.x_min_entry.get())
        xmax = float(self.view.sidepanel.x_max_entry.get())
        ymin = float(self.view.sidepanel.y_min_entry.get())
        ymax = float(self.view.sidepanel.y_max_entry.get())

        #might need a way to refresh the figure to handle mutliple scans / zooming
        #especially if the x/y range is changed.
        #https://stackoverflow.com/questions/41458139/refresh-matplotlib-figure-in-a-tkinter-app

        self.model.set_scan_range(xmin, xmax, ymin, ymax)
        self.model.step_size = float(self.view.sidepanel.step_size_entry.get())
        self.model.set_num_data_samples_per_batch(int(self.view.sidepanel.n_sample_size_entry.get()))

        self.model.reset()
        self.model.start()

        self.scan_thread = Thread(target=self.scan_thread_function)
        self.scan_thread.start()

    def on_closing(self):
        try:
            self.stop_scan()
            self.root.quit()
            self.root.destroy()
        except Exception as e:
            logger.debug(e)
            pass

def build_data_scanner():
    if args.randomtest:
        scanner = datasources.RandomPiezoScanner(controller=None)
    else:
        controller = nipiezojenapy.PiezoControl(device_name = args.daq_name,
                                  write_channels = args.piezo_write_channels.split(','),
                                  read_channels = args.piezo_read_channels.split(','))

        data_acq = datasources.NiDaqSampler(args.daq_name,
                             args.signal_terminal,
                             args.clock_rate,
                             args.num_data_samples_per_batch,
                             args.clock_terminal,
                             args.rwtimeout,
                             args.signal_counter)

        scanner = datasources.NiDaqPiezoScanner(data_acq, controller)

    return scanner


def main():
    tkapp = MainTkApplication(build_data_scanner())
    tkapp.run()

if __name__ == '__main__':
    main()

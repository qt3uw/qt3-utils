import time
import argparse
import collections
import tkinter as tk
import tkinter.ttk as ttk
import logging
from threading import Thread

import numpy as np
import scipy.optimize
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib
matplotlib.use('Agg')
import nidaqmx

import qt3utils.nidaq
import qt3utils.datagenerators as datasources
import qt3utils.datagenerators.piezoscanner
import nipiezojenapy


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
parser.add_argument('-n', '--num-data-samples-per-batch', metavar = 'N', default = 25, type=int,
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
parser.add_argument('-cmap', metavar = '<MPL color>', default = 'Reds',
                    help='Set the MatplotLib colormap scale')
args = parser.parse_args()

logger = logging.getLogger(__name__)
logging.basicConfig()

if args.quiet is False:
    logger.setLevel(logging.INFO)


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
            data[np.isinf(data)] = 0 #protect against +-inf
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
            #todo: draw a circle around clicked point? Maybe with a high alpha, so that its faint
            self.onclick_callback(event)

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
        tk.Label(frame, text="DAQ Settings", font='Helvetica 16').grid(row=row, column=0,pady=10)
        row += 1
        tk.Label(frame, text="N samples/step").grid(row=row, column=0)
        self.n_sample_size_value = tk.IntVar()
        self.n_sample_size_entry = tk.Entry(frame, width=10, textvariable = self.n_sample_size_value)
        self.n_sample_size_entry.grid(row=row, column=1)
        self.n_sample_size_value.set(args.num_data_samples_per_batch)


        row += 1
        tk.Label(frame, text="View Settings", font='Helvetica 16').grid(row=row, column=0, pady=10)
        row += 1
        self.set_color_map_button = tk.Button(frame, text="Set Color")
        self.set_color_map_button.grid(row=row, column=0, pady=(2,15))
        self.mpl_color_map_entry = tk.Entry(frame, width=10)
        self.mpl_color_map_entry.insert(10, 'Reds')
        self.mpl_color_map_entry.grid(row=row, column=1, pady=(2,15))

        self.log10Button = tk.Button(frame, text="Log10")
        self.log10Button.grid(row=row, column=2, pady=(2,15))


    def update_go_to_position(self, x = None, y = None, z = None):
        if x is not None:
            self.go_to_x_position_text.set(np.round(x,4))
        if y is not None:
            self.go_to_y_position_text.set(np.round(y,4))
        if z is not None:
            self.z_entry_text.set(np.round(z,4))

    def mpl_onclick_callback(self, mpl_event):
        if mpl_event.xdata and mpl_event.ydata:
            self.update_go_to_position(mpl_event.xdata, mpl_event.ydata)


class MainApplicationView():
    def __init__(self, main_frame, scan_range = [0,80]):
        frame = tk.Frame(main_frame)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scan_view = ScanImage(args.cmap)
        self.sidepanel = SidePanel(main_frame, scan_range)
        self.scan_view.set_onclick_callback(self.sidepanel.mpl_onclick_callback)

        self.canvas = FigureCanvasTkAgg(self.scan_view.fig, master=frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(self.canvas, frame)
        toolbar.update()
        self.canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.canvas.draw()

    def show_optimization_plot(self, title, old_opt_value,
                                     new_opt_value,
                                     x_vals,
                                     y_vals, fit_coeff = None):
        win = tk.Toplevel()
        win.title(title)
        fig, ax = plt.subplots()
        ax.set_xlabel('position (um)')
        ax.set_ylabel('count rate (Hz)')
        ax.plot(x_vals, y_vals, label='data')
        ax.ticklabel_format(style='sci',scilimits=(0,3))
        ax.axvline(old_opt_value, linestyle='--', color='red', label=f'old position {old_opt_value:.2f}')
        ax.axvline(new_opt_value, linestyle='-', color='blue', label=f'new position {new_opt_value:.2f}')

        if fit_coeff is not None:
            y_fit = qt3utils.datagenerators.piezoscanner.gauss(x_vals, *fit_coeff)
            ax.plot(x_vals, y_fit, label='fit', color='orange')

        ax.legend()

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(canvas, win)
        toolbar.update()
        canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        canvas.draw()

class MainTkApplication():

    def __init__(self, data_model):
        self.root = tk.Tk()
        self.model = data_model
        scan_range = [data_model.controller.minimum_allowed_position,
                      data_model.controller.maximum_allowed_position]
        self.view = MainApplicationView(self.root, scan_range)
        self.view.sidepanel.startButton.bind("<Button>", self.start_scan)
        self.view.sidepanel.stopButton.bind("<Button>", self.stop_scan)
        self.view.sidepanel.log10Button.bind("<Button>", self.log_scan_image)
        self.view.sidepanel.gotoButton.bind("<Button>", self.go_to_position)
        self.view.sidepanel.go_to_z_button.bind("<Button>", self.go_to_z)
        self.view.sidepanel.saveScanButton.bind("<Button>", self.save_scan)
        self.view.sidepanel.set_color_map_button.bind("<Button>", self.set_color_map)

        self.view.sidepanel.optimize_x_button.bind("<Button>", lambda e: self.optimize('x'))
        self.view.sidepanel.optimize_y_button.bind("<Button>", lambda e: self.optimize('y'))
        self.view.sidepanel.optimize_z_button.bind("<Button>", lambda e: self.optimize('z'))

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.scan_thread = None

        self.optimized_position = {'x':0, 'y':0, 'z':-1}
        if self.model.controller:
            self.optimized_position['z'] = self.model.controller.get_current_position()[2]
        else:
            self.optimized_position['z'] = 20
        self.view.sidepanel.z_entry_text.set(np.round(self.optimized_position['z'],4))


    def run(self):
        self.root.title("QT3Scan: Piezo Controlled NIDAQ Digital Count Rate Scanner")
        self.root.deiconify()
        self.root.mainloop()

    def go_to_position(self, event = None):
        if self.model.controller:
            self.model.controller.go_to_position(x = self.view.sidepanel.go_to_x_position_text.get(), y = self.view.sidepanel.go_to_y_position_text.get())
        else:
            print(f'controller would have moved to x,y = {self.view.sidepanel.go_to_x_position_text.get():.2f}, {self.view.sidepanel.go_to_y_position_text.get():.2f}')
        self.optimized_position['x'] = self.view.sidepanel.go_to_x_position_text.get()
        self.optimized_position['y'] = self.view.sidepanel.go_to_y_position_text.get()

    def go_to_z(self, event = None):
        if self.model.controller:
            self.model.controller.go_to_position(z = self.view.sidepanel.z_entry_text.get())
        else:
            print(f'controller would have moved to z = {self.view.sidepanel.z_entry_text.get():.2f}')
        self.optimized_position['z'] = self.view.sidepanel.z_entry_text.get()

    def set_color_map(self, event = None):
        #Is there a way for this function to exist entirely in the view code instead of here?
        self.view.scan_view.cmap = self.view.sidepanel.mpl_color_map_entry.get()
        if len(self.model.data) > 0:
            self.view.scan_view.update(self.model)
            self.view.canvas.draw()

    def log_scan_image(self, event = None):
        #Is there a way for this function to exist entirely in the view code instead of here?
        self.view.scan_view.log_data = not self.view.scan_view.log_data
        if len(self.model.data) > 0:
            self.view.scan_view.update(self.model)
            self.view.canvas.draw()

    def stop_scan(self, event = None):
        self.model.stop()

    def scan_thread_function(self, xmin, xmax, ymin, ymax, step_size, N):

        self.model.set_scan_range(xmin, xmax, ymin, ymax)
        self.model.step_size = step_size
        self.model.set_num_data_samples_per_batch(N)

        try:
            self.model.reset() #clears the data
            self.model.start() #starts the DAQ
            self.model.set_to_starting_position() #moves the stage to starting position

            while self.model.still_scanning():
                self.model.scan_x()
                self.view.scan_view.update(self.model)
                self.view.canvas.draw()
                self.model.move_y()
        except nidaqmx.errors.DaqError as e:
            logger.info(e)
            logger.info('Check for other applications using resources. If not, you may need to restart the application.')

        self.view.sidepanel.startButton['state'] = 'normal'
        self.view.sidepanel.go_to_z_button['state'] = 'normal'
        self.view.sidepanel.gotoButton['state'] = 'normal'
        self.view.sidepanel.saveScanButton['state'] = 'normal'

        self.view.sidepanel.optimize_x_button['state'] = 'normal'
        self.view.sidepanel.optimize_y_button['state'] = 'normal'
        self.view.sidepanel.optimize_z_button['state'] = 'normal'

    def start_scan(self, event = None):
        self.view.sidepanel.startButton['state'] = 'disabled'
        self.view.sidepanel.go_to_z_button['state'] = 'disabled'
        self.view.sidepanel.gotoButton['state'] = 'disabled'
        self.view.sidepanel.saveScanButton['state'] = 'disabled'

        self.view.sidepanel.optimize_x_button['state'] = 'disabled'
        self.view.sidepanel.optimize_y_button['state'] = 'disabled'
        self.view.sidepanel.optimize_z_button['state'] = 'disabled'

        #clear the figure
        self.view.scan_view.reset()

        #get the scan settings
        xmin = float(self.view.sidepanel.x_min_entry.get())
        xmax = float(self.view.sidepanel.x_max_entry.get())
        ymin = float(self.view.sidepanel.y_min_entry.get())
        ymax = float(self.view.sidepanel.y_max_entry.get())

        args = [xmin, xmax, ymin, ymax]
        args.append(float(self.view.sidepanel.step_size_entry.get()))
        args.append(int(self.view.sidepanel.n_sample_size_value.get()))

        self.scan_thread = Thread(target=self.scan_thread_function,
                                  args = args)
        self.scan_thread.start()

    def save_scan(self, event = None):
        myformats = [('Numpy Array', '*.npy')]
        afile = tk.filedialog.asksaveasfilename(filetypes = myformats, defaultextension = '.npy')
        logger.info(afile)
        if afile is None or afile == '':
           return #selection was canceled.
        with open(afile, 'wb') as f_object:
          np.save(f_object, self.model.data)

        self.view.sidepanel.saveScanButton['state'] = 'normal'

    def optimize_thread_function(self, axis, central, range, step_size):

        try:
            data, axis_vals, opt_pos, coeff = self.model.optimize_position(axis,
                                                                           central,
                                                                           range,
                                                                           step_size)
            self.optimized_position[axis] = opt_pos
            self.model.controller.go_to_position(**{axis:opt_pos})
            self.view.show_optimization_plot(f'Optimize {axis}',
                                             central,
                                             self.optimized_position[axis],
                                             axis_vals,
                                             data,
                                             coeff)
            self.view.sidepanel.update_go_to_position(**{axis:self.optimized_position[axis]})

        except nidaqmx.errors.DaqError as e:
            logger.info(e)
            logger.info('Check for other applications using resources. If not, you may need to restart the application.')


        self.view.sidepanel.startButton['state'] = 'normal'
        self.view.sidepanel.stopButton['state'] = 'normal'
        self.view.sidepanel.go_to_z_button['state'] = 'normal'
        self.view.sidepanel.gotoButton['state'] = 'normal'
        self.view.sidepanel.saveScanButton['state'] = 'normal'

        self.view.sidepanel.optimize_x_button['state'] = 'normal'
        self.view.sidepanel.optimize_y_button['state'] = 'normal'
        self.view.sidepanel.optimize_z_button['state'] = 'normal'

    def optimize(self, axis):

        opt_range = float(self.view.sidepanel.optimize_range_entry.get())
        opt_step_size = float(self.view.sidepanel.optimize_step_size_entry.get())
        old_optimized_value = self.optimized_position[axis]

        self.model.set_num_data_samples_per_batch(self.view.sidepanel.n_sample_size_value.get())

        self.view.sidepanel.startButton['state'] = 'disabled'
        self.view.sidepanel.stopButton['state'] = 'disabled'
        self.view.sidepanel.go_to_z_button['state'] = 'disabled'
        self.view.sidepanel.gotoButton['state'] = 'disabled'
        self.view.sidepanel.saveScanButton['state'] = 'disabled'

        self.view.sidepanel.optimize_x_button['state'] = 'disabled'
        self.view.sidepanel.optimize_y_button['state'] = 'disabled'
        self.view.sidepanel.optimize_z_button['state'] = 'disabled'

        self.optimize_thread = Thread(target=self.optimize_thread_function,
                                      args = (axis, old_optimized_value, opt_range, opt_step_size))
        self.optimize_thread.start()

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
        controller = nipiezojenapy.BaseControl()
        scanner = datasources.RandomPiezoScanner(controller=controller)
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

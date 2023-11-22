import argparse
import tkinter as tk
import logging
from threading import Thread

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib
import nidaqmx
import nipiezojenapy
from qt3utils.nidaq.customcontrollers import VControl
from qt3utils.datagenerators import PLEscanner

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
parser.add_argument('--wavelength-write-channel', metavar = 'ch0', default = 'ao0', type=str,
                    help='Analog output channel used to control the wavelength of the laser')
parser.add_argument('--wavelength-read-channel', metavar = 'ch0', default = 'ai0', type=str,
                    help='Analog input channels used to read the instantaneous wavelength')
parser.add_argument('-lmin', '--wavelength-min-position', metavar = 'voltage', default = -10, type=float,
                    help='sets min allowed voltage on PLE controller.')
parser.add_argument('-lmax', '--wavelength-max-position', metavar = 'voltage', default = 10, type=float,
                    help='sets min allowed voltage on PLE controller.')
parser.add_argument('-lscale', '--wavelength-scale-nm-per-volt', default = 1, type=float,
                    help='sets nanometer to volt scale for PLE controller.')
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

    def update(self, model):

        if self.log_data:
            data = np.log10(model.scanned_count_rate)
            data[np.isinf(data)] = 0 #protect against +-inf
        else:
            data = model.scanned_count_rate

        self.artist = self.ax.imshow(data, cmap=self.cmap, extent=[model.vmin,
                                                                   model.vmax + model.step_size,
                                                                   model.current_t + model.raster_line_pause,
                                                                   model.rate_counter.num_data_samples_per_batch])
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
        pass

class SidePanel():
    def __init__(self, root, scan_range):
        frame = tk.Frame(root)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        row = 0
        tk.Label(frame, text="Scan Settings", font='Helvetica 16').grid(row=row, column=0,pady=10)
        row += 1
        self.startButton = tk.Button(frame, text="Start Scan")
        self.startButton.grid(row=row, column=0)
        row += 1
        tk.Label(frame, text="Voltage Range (V)").grid(row=row, column=0)
        self.v_min_entry = tk.Entry(frame, width=10)
        self.v_max_entry = tk.Entry(frame, width=10)
        self.v_min_entry.insert(10, scan_range[0])
        self.v_max_entry.insert(10, scan_range[1])
        self.v_min_entry.grid(row=row, column=1)
        self.v_max_entry.grid(row=row, column=2)

        row += 1
        tk.Label(frame, text="Number of Pixels").grid(row=row, column=0)
        self.num_pixels= tk.Entry(frame, width=10)
        self.num_pixels.insert(10, 150)
        self.num_pixels.grid(row=row, column=1)

        row += 1
        tk.Label(frame, text="Number of Scans").grid(row=row, column=0)
        self.scan_num_entry = tk.Entry(frame, width=10)
        self.scan_num_entry.insert(10, 10)
        self.scan_num_entry.grid(row=row, column=1)

        row += 1
        tk.Label(frame, text="Sweep Time").grid(row=row, column=0)
        self.sweep_time_entry = tk.Entry(frame, width=10)
        self.sweep_time_entry.insert(10, 3)
        self.sweep_time_entry.grid(row=row, column=1)

        row += 1
        tk.Label(frame, text="DAQ Settings", font='Helvetica 16').grid(row=row, column=0,pady=10)

        row += 1
        self.GotoButton = tk.Button(frame, text="Go To Voltage")
        self.GotoButton.grid(row=row, column=0)
        row += 1
        tk.Label(frame, text="Voltage (V)").grid(row=row, column=0)
        self.v_entry = tk.Entry(frame, width=10)
        self.v_entry.insert(10, 0)
        self.v_entry.grid(row=row, column=1)

        row += 1
        tk.Label(frame, text="Voltage Limits (V)").grid(row=row, column=0)
        self.v_lmin_entry = tk.Entry(frame, width=10)
        self.v_lmax_entry = tk.Entry(frame, width=10)
        self.v_lmin_entry.insert(10, float(args.wavelength_min_position))
        self.v_lmax_entry.insert(10, float(args.wavelength_max_position))
        self.v_lmin_entry.grid(row=row, column=1)
        self.v_lmax_entry.grid(row=row, column=2)



class MainApplicationView():
    def __init__(self, main_frame, scan_range = [-3, 5]):
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

    def __init__(self, counter_scanner):
        self.counter_scanner = counter_scanner
        self.root = tk.Tk()
        self.view = MainApplicationView(self.root)
        self.view.sidepanel.startButton.bind("<Button>", self.start_scan)
        self.view.sidepanel.GotoButton.bind("<Button>", self.go_to_voltage)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def go_to_voltage(self, event = None):
        self.view.sidepanel.startButton['state'] = 'disabled'
        self.view.sidepanel.GotoButton['state'] = 'disabled'
        self.counter_scanner.go_to_v(float(self.view.sidepanel.v_entry.get()))
        self.view.sidepanel.startButton['state'] = 'normal'
        self.view.sidepanel.GotoButton['state'] = 'normal'

    #TODO: add device/channel name, change functionality to nidaq, add sweep loop and sleep() with settling time
    def start_scan(self, event = None):
        self.view.sidepanel.startButton['state'] = 'disabled'
        self.view.sidepanel.GotoButton['state'] = 'disabled'

        n_sample_size = int(self.view.sidepanel.num_pixels.get())
        sweep_time_entry = float(self.view.sidepanel.sweep_time_entry.get())
        vmin = float(self.view.sidepanel.v_min_entry.get())
        vmax = float(self.view.sidepanel.v_max_entry.get())
        step_size = (vmax - vmin) / float(n_sample_size)
        args = [vmin, vmax]
        args.append(step_size)
        args.append(n_sample_size)

        settling_time = sweep_time_entry / n_sample_size
        self.counter_scanner.wavelength_controller.settling_time_in_seconds = settling_time

        self.scan_thread = Thread(target=self.scan_thread_function, args = args)
        self.scan_thread.start()


        #with nidaqmx.Task() as task:
        #    task.ao_channels.add_ao_voltage_chan("Dev1/ai0")
        #    task.write(xmin)

    def run(self):
        self.root.title("QT3PLE: Run PLE scan")
        self.root.deiconify()
        self.root.mainloop()

    def stop_scan(self, event = None):
        self.counter_scanner.stop()

    def on_closing(self):
        try:
            self.stop_scan()
            self.root.quit()
            self.root.destroy()
        except Exception as e:
            logger.debug(e)
            pass

    def scan_thread_function(self, vmin, vmax, step_size, N):

        self.counter_scanner.set_scan_range(vmin, vmax)
        self.counter_scanner.step_size = step_size
        self.counter_scanner.set_num_data_samples_per_batch(N)

        try:
            self.counter_scanner.reset()  # clears the data
            self.counter_scanner.start()  # starts the DAQ
            self.counter_scanner.set_to_starting_position()  # moves the stage to starting position

            while self.counter_scanner.still_scanning():
                self.counter_scanner.scan_v()
                self.view.scan_view.update(self.counter_scanner)
                self.view.canvas.draw()

            self.counter_scanner.stop()

        except nidaqmx.errors.DaqError as e:
            logger.info(e)
            logger.info(
                'Check for other applications using resources. If not, you may need to restart the application.')

        self.view.sidepanel.startButton['state'] = 'normal'
        self.view.sidepanel.GotoButton['state'] = 'normal'

def build_data_scanner():

    if args.randomtest:
        data_acq = datasources.RandomRateCounter(simulate_single_light_source=True,
                                                 num_data_samples_per_batch=args.num_data_samples_per_batch)
    else:
        data_acq = datasources.NiDaqDigitalInputRateCounter(args.daq_name,
                                                            args.signal_terminal,
                                                            args.clock_rate,
                                                            args.num_data_samples_per_batch,
                                                            args.clock_terminal,
                                                            args.rwtimeout,
                                                            args.signal_counter)

    voltage_controller = VControl(device_name = args.daq_name,
                                  write_channel = args.wavelength_write_channel,
                                  read_channel = args.wavelength_read_channel,
                                  min_position = args.wavelength_min_position,
                                  max_position = args.wavelength_max_position,
                                  scale_nm_per_volt = args.wavelength_scale_nm_per_volt)

    scanner = PLEscanner.CounterAndScanner(data_acq, voltage_controller)

    return scanner

def main():
    tkapp = MainTkApplication(build_data_scanner())
    tkapp.run()


if __name__ == '__main__':
    main()

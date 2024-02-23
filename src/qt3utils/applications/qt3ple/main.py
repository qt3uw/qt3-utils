import argparse
import h5py
import importlib
import importlib.resources
import logging
from threading import Thread

import matplotlib
from matplotlib import gridspec
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.pyplot as plt
import nidaqmx
import numpy as np
import tkinter as tk
import yaml

from qt3utils.datagenerators import plescanner

matplotlib.use('Agg')

parser = argparse.ArgumentParser(description='NI DAQ (PCIx 6363) / PLE Scanner',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('-q', '--quiet', action='store_true',
                    help='When true,logger level will be set to warning. Otherwise, set to "info".')
parser.add_argument('-cmap', metavar='<MPL color>', default='gray',
                    help='Set the MatplotLib colormap scale')
args = parser.parse_args()

logger = logging.getLogger(__name__)
logging.basicConfig()

if args.quiet is False:
    logger.setLevel(logging.INFO)

NIDAQ_DEVICE_NAMES = ['NIDAQ Rate Counter', "Lockin & Wavemeter"]
RANDOM_DAQ_DEVICE_NAME = 'Random Data Generator'

DEFAULT_DAQ_DEVICE_NAME = NIDAQ_DEVICE_NAMES[0]

CONTROLLER_PATH = 'qt3utils.applications.controller'
STANDARD_CONTROLLERS = {NIDAQ_DEVICE_NAMES[0] : 'nidaq_rate_counter.yaml',
                        NIDAQ_DEVICE_NAMES[1] : 'nidaq_wm_ple.yaml'}

class ScanImage:
    def __init__(self, mplcolormap='gray') -> None:
        self.fig = plt.figure()
        self.ax = plt.gca()
        self.cbar = None
        self.cmap = mplcolormap
        self.cid = self.fig.canvas.mpl_connect('button_press_event', self.onclick)
        self.log_data = False

    def fill_subplot(self, x, y):
        if self.ax is None:
            self.ax = plt.gca()
        sub_plt = self.ax.plot(x, y)
        return sub_plt

    def update_image_and_plot(self, model) -> None:
        num_readers = len(model.readers)
        grid = plt.GridSpec(2, num_readers)
        self.update_image(model, grid)
        self.update_plot(model, grid)


    def update_image(self, model, grid) -> None:
        for ii, reader in enumerate(model.readers):

            if self.log_data:
                data = np.log10(model.scanned_count_rate)
                data[np.isinf(data)] = 0  # protect against +-inf
            else:
                data = model.scanned_count_rate
            data = np.array(data).T.tolist()

            artist = self.ax.imshow(data, plt.subplot(grid[0, ii]), cmap=self.cmap)
                                   # , extent=[model.current_frame + model.raster_line_pause,
                                   #                                    0,
                                   #                                    model.vstart,
                                   #                                    model.vend + model.step_size]
            if self.cbar is None:
                self.cbar = self.fig.colorbar(artist, ax=self.ax)
            else:
                self.cbar.update_normal(artist)

            if self.log_data is False:
                self.cbar.formatter.set_powerlimits((0, 3))

            self.ax.set_xlabel('Pixels')
            self.ax.set_ylabel('Voltage (V)')

    def update_plot(self, model, grid) -> None:

        for ii, reader in enumerate(model.readers):
            y_data = model.readers[reader]
            x_control = model.scanned_control
            self.ax.plot(x_control, y_data, plt.subplot(grid[1, ii]), color='k', linewidth=1.5)

    def reset(self) -> None:
        self.ax.cla()

    def set_onclick_callback(self, f) -> None:
        self.onclick_callback = f

    def onclick(self, event) -> None:
        pass


class SidePanel():
    def __init__(self, root, scan_range) -> None:
        frame = tk.Frame(root.root)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        row = 0
        tk.Label(frame, text="Scan Settings", font='Helvetica 16').grid(row=row, column=0, pady=10)
        row += 1
        self.start_button = tk.Button(frame, text="Start Scan")
        self.start_button.grid(row=row, column=0)
        self.stop_button = tk.Button(frame, text="Stop Scan")
        self.stop_button.grid(row=row, column=1)
        self.save_scan_button = tk.Button(frame, text="Save Scan")
        self.save_scan_button.grid(row=row, column=2)
        row += 1
        tk.Label(frame, text="Voltage Range (V)").grid(row=row, column=0)
        self.voltage_start_entry = tk.Entry(frame, width=10)
        self.voltage_end_entry = tk.Entry(frame, width=10)
        self.voltage_start_entry.insert(10, scan_range[0])
        self.voltage_end_entry.insert(10, scan_range[1])
        self.voltage_start_entry.grid(row=row, column=1)
        self.voltage_end_entry.grid(row=row, column=2)

        row += 1
        tk.Label(frame, text="Number of Pixels").grid(row=row, column=0)
        self.num_pixels = tk.Entry(frame, width=10)
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
        tk.Label(frame, text="DAQ Settings", font='Helvetica 16').grid(row=row, column=0, pady=10)

        row += 1
        self.goto_button = tk.Button(frame, text="Go To Voltage")
        self.goto_button.grid(row=row, column=0)
        row += 1
        tk.Label(frame, text="Voltage (V)").grid(row=row, column=0)
        self.voltage_entry = tk.Entry(frame, width=10)
        self.voltage_entry.insert(10, 0)
        self.voltage_entry.grid(row=row, column=1)

        row += 1
        tk.Label(frame, text="Voltage Limits (V)").grid(row=row, column=0)
        self.voltage_lmin_entry = tk.Entry(frame, width=10)
        self.voltage_lmax_entry = tk.Entry(frame, width=10)
        self.voltage_lmin_entry.insert(10, float(scan_range[0]))
        self.voltage_lmax_entry.insert(10, float(scan_range[1]))
        self.voltage_lmin_entry.grid(row=row, column=1)
        self.voltage_lmax_entry.grid(row=row, column=2)

        row+=1
        self.controller_option = tk.StringVar(frame)
        self.controller_option.set(DEFAULT_DAQ_DEVICE_NAME)  # setting the default value

        self.controller_menu = tk.OptionMenu(frame,
                                             self.controller_option,
                                             *STANDARD_CONTROLLERS.keys(),
                                             command=root.load_controller_from_name)

        self.controller_menu.grid(row=row, column=0, columnspan=3)

        row += 1
        self.hardware_config_from_yaml_button = tk.Button(frame, text="Load YAML Config")
        self.hardware_config_from_yaml_button.grid(row=row, column=0, columnspan=3)


class MainApplicationView():
    def __init__(self, main_frame, scan_range=[-3, 5]) -> None:
        frame = tk.Frame(main_frame.root)
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

    def __init__(self, controller_name) -> None:
        #self.counter_scanner = counter_scanner
        self.root = tk.Tk()
        self.view = MainApplicationView(self)
        self.view.controller_option = controller_name
        # data acquisition model that is used to acquire data
        self.data_acquisition_models = {}
        self.controller_models = {}
        # load the data acquisition model
        self.view.sidepanel.start_button.bind("<Button>", self.start_scan)
        self.view.sidepanel.save_scan_button.bind("<Button>", self.save_scan)
        self.view.sidepanel.stop_button.bind("<Button>", self.stop_scan)
        self.view.sidepanel.goto_button.bind("<Button>", self.go_to_voltage)
        self.view.sidepanel.hardware_config_from_yaml_button.bind("<Button>", lambda e: self.configure_from_yaml())
        self.root.protocol("WM_DELETE_WINDOWwait_visibility()", self.on_closing)

    def go_to_voltage(self, event=None) -> None:
        self.disable_buttons()
        self.application_controller.go_to_voltage(float(self.view.sidepanel.voltage_entry.get()))
        self.enable_buttons()

    def start_scan(self, event=None) -> None:
        self.disable_buttons()

        n_sample_size = int(self.view.sidepanel.num_pixels.get())
        n_scans = int(self.view.sidepanel.scan_num_entry.get())
        sweep_time_entry = float(self.view.sidepanel.sweep_time_entry.get())
        vstart= float(self.view.sidepanel.voltage_start_entry.get())
        vend = float(self.view.sidepanel.voltage_end_entry.get())
        step_size = (vend - vstart) / float(n_sample_size)
        args = [vstart, vend]
        args.append(step_size)
        args.append(n_sample_size)
        args.append(n_scans)

        settling_time = sweep_time_entry / n_sample_size
        self.application_controller.wavelength_controller.settling_time_in_seconds = settling_time

        self.scan_thread = Thread(target=self.scan_thread_function, args=args)
        self.scan_thread.start()

    def run(self) -> None:
        self.root.title("QT3PLE: Run PLE scan")
        self.root.deiconify()
        self.root.mainloop()

    def stop_scan(self, event=None) -> None:
        self.application_controller.stop()
        self.enable_buttons()
    def on_closing(self) -> None:
        try:
            self.stop_scan()
            self.root.quit()
            self.root.destroy()
        except Exception as e:
            logger.debug(e)
            pass

    def scan_thread_function(self, vstart: float, vend: float, step_size: float, n_sample_size: int, n_scans: int) -> None:
        """
        Function to be called in background thread
        Scans the voltage from vstart to vend in increments of step_size
        for a total of n_sample_size data points n_scans number of times
        """

        self.application_controller.set_scan_range(vstart, vend)
        self.application_controller.step_size = step_size
        self.application_controller.tmax = n_scans
        try:
            self.application_controller.reset()  # clears the data
            self.application_controller.start()  # starts the DAQ
            self.application_controller.set_to_starting_voltage()  # moves the stage to starting voltage

            while self.application_controller.still_scanning():
                self.application_controller.scan_wavelengths()
                self.view.scan_view.update_image_and_plot(self.application_controller)
                self.view.canvas.draw()

            self.application_controller.stop()

        except nidaqmx.errors.DaqError as e:
            logger.info(e)
            logger.info(
                'Check for other applications using resources. If not, you may need to restart the application.')

        self.enable_buttons()

    def save_scan(self, event = None):
        myformats = [('Compressed Numpy MultiArray', '*.npz'), ('Numpy Array (count rate only)', '*.npy'), ('HDF5', '*.h5')]
        afile = tk.filedialog.asksaveasfilename(filetypes=myformats, defaultextension='.npz')
        logger.info(afile)
        file_type = afile.split('.')[-1]
        if afile is None or afile == '':
            return # selection was canceled.

        data = dict(
            raw_counts=self.application_controller.scanned_raw_counts,
            count_rate=self.application_controller.scanned_count_rate,
            scan_range=self.application_controller.get_completed_scan_range(),
            step_size=self.application_controller.step_size,
            daq_clock_rate=self.application_controller.rate_counter.clock_rate,
        )

        if file_type == 'npy':
            np.save(afile, data['count_rate'])

        if file_type == 'npz':
            np.savez_compressed(afile, **data)

        elif file_type == 'h5':
            h5file = h5py.File(afile, 'w')
            for key, value in data.items():
                h5file.create_dataset(key, data=value)
            h5file.close()

    def configure_from_yaml(self, afile=None) -> None:
        """
        This method launches a GUI window to allow the user to select a yaml file to configure the data controller.
        Or it loads a specified configuration yaml file.
        It will attempt to configure the hardware specified in the configuration file and instantiate a controller class
        """
        filetypes = (
            ('YAML', '*.yaml'),
        )
        if not afile:
            afile = tk.filedialog.askopenfile(filetypes=filetypes, defaultextension='.yaml')
            if afile is None:
                return  # selection was canceled.
            config = yaml.safe_load(afile)
            afile.close()
        else:
            with open(afile, 'r') as file:
                config = yaml.safe_load(file)

        CONFIG_FILE_APPLICATION_NAME = list(config.keys())[0]

        self.app_controller_config = config[CONFIG_FILE_APPLICATION_NAME]["ApplicationController"]
        self.app_config = self.app_controller_config["configure"]
        logger.info("load settings from yaml")
        daq_readers = self.app_config["readers"]["daq_readers"]
        if daq_readers is not None:
            for daq_reader in daq_readers:
                daq_reader_name = daq_readers[daq_reader]
                daq_reader_config = config[CONFIG_FILE_APPLICATION_NAME][daq_reader_name]
                module = importlib.import_module(daq_reader_config['import_path'])
                logger.debug(f"loading {daq_reader_config['import_path']}")
                cls = getattr(module, daq_reader_config['class_name'])
                self.data_acquisition_models[daq_reader] = cls(logger.level)
                self.data_acquisition_models[daq_reader].configure(daq_reader_config['configure'])
        wm_readers = self.app_config["readers"]["wm_readers"]
        if wm_readers is not None:
            for wm_reader in wm_readers:
                wm_reader_name = wm_readers[wm_reader]
                wm_reader_config = config[CONFIG_FILE_APPLICATION_NAME][wm_reader_name]
                module = importlib.import_module(wm_reader_config['import_path'])
                logger.debug(f"loading {wm_reader_config['import_path']}")
                cls = getattr(module, wm_reader_config['class_name'])
                self.data_acquisition_models[wm_reader] = cls(logger.level)
                self.data_acquisition_models[wm_reader].configure(wm_reader_config['configure'])
        daq_controller_config = config[CONFIG_FILE_APPLICATION_NAME]
        if daq_controller_config is not None:
            module = importlib.import_module(daq_controller_config['import_path'])
            logger.debug(f"loading {daq_controller_config['import_path']}")
            cls = getattr(module, daq_controller_config['class_name'])
            controller_model = cls(logger.level)
            controller_model.configure(daq_controller_config['configure'])
        else:
           raise Exception("Yaml configuration file must have a controller for PLE scan.")
        self.application_controller = plescanner.PleScanner(self.data_acquisition_models, controller_model)

    def load_controller_from_name(self, application_controller_name: str) -> None:
        """
        Loads the default yaml configuration file for the application controller.

        Should be called during instantiation of this class and should be the callback
        function for the support controller pull-down menu in the side panel
        """
        yaml_path = importlib.resources.files(CONTROLLER_PATH).joinpath(STANDARD_CONTROLLERS[application_controller_name])
        self.configure_from_yaml(str(yaml_path))

    def disable_buttons(self):
        self.view.sidepanel.start_button['state'] = 'disabled'
        self.view.sidepanel.goto_button['state'] = 'disabled'
        self.view.sidepanel.controller_menu.config(state=tk.DISABLED)
        self.view.sidepanel.save_scan_button.config(state=tk.DISABLED)

    def enable_buttons(self):
        self.view.sidepanel.start_button['state'] = 'normal'
        self.view.sidepanel.goto_button['state'] = 'normal'
        self.view.sidepanel.controller_menu.config(state=tk.NORMAL)
        self.view.sidepanel.save_scan_button.config(state=tk.NORMAL)

def main() -> None:
    tkapp = MainTkApplication(DEFAULT_DAQ_DEVICE_NAME)
    tkapp.run()


if __name__ == '__main__':
    main()

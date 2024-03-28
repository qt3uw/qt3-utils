import argparse
import importlib
import importlib.resources
import logging
import pickle
from threading import Thread

import matplotlib
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

CONTROLLER_PATH = 'qt3utils.applications.controllers'
STANDARD_CONTROLLERS = {NIDAQ_DEVICE_NAMES[0] : 'nidaq_rate_counter.yaml',
                        NIDAQ_DEVICE_NAMES[1] : 'nidaq_wm_ple.yaml'}

SCAN_OPTIONS = ["Discrete", "Batches"]

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
        for ax in self.fig.axes:
            self.fig.delaxes(ax)
        num_readers = len(model.readers)
        grid = plt.GridSpec(2, num_readers)
        self.update_image(model, grid)
        self.update_plot(model, grid)

    def update_image(self, model, grid) -> None:
        for ii, reader in enumerate(model.readers):
            y_data = []
            for output in model.outputs:
                y_scan = output[reader]
                if isinstance(y_scan[0], list) or isinstance(y_scan[0], np.ndarray):
                    for jj, ydatum in enumerate(y_scan):
                        y_scan[jj] = np.mean(np.array(ydatum))
                y_data.append(y_scan)

            ax = self.fig.add_subplot(grid[0, ii])
            y_data = np.array(y_data).T
            artist = ax.imshow(y_data, cmap=self.cmap
                                    , extent=[model.current_frame + model.wavelength_controller.settling_time_in_seconds,
                                                                       0.0,
                                                                       model.get_start,
                                                                       model.get_end + model.step_size])
            cbar = self.fig.colorbar(artist, ax=ax)

            #if self.log_data is False:
            #    cbar.formatter.set_powerlimits((0, 3))

            self.ax.set_xlabel('Pixels')
            self.ax.set_ylabel('Voltage (V)')

    def update_plot(self, model, grid) -> None:

        for ii, reader in enumerate(model.readers):
            y_data = model.outputs[model.current_frame-1][reader]
            x_control = model.scanned_control[model.current_frame-1]
            ax = self.fig.add_subplot(grid[1, ii])
            ax.plot(x_control, y_data, color='k', linewidth=1.5)

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
        tk.Label(frame, text="Scan Range").grid(row=row, column=0)
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
        self.do_downsweep = tk.IntVar(value=0)
        tk.Label(frame, text="Backward Sweep Time").grid(row=row, column=0)
        self.downsweep_time_entry = tk.Entry(frame, width=10)
        self.downsweep_time_entry.insert(10, 1)
        self.downsweep_time_entry.grid(row=row, column=1)
        self.downsweep_time_entry.config(state=tk.DISABLED)
        self.downsweep_button = tk.Checkbutton(frame, text="Downsweep", onvalue=1, offvalue=0,
                                               variable=self.do_downsweep, command=self.display_downsweep_time)
        self.downsweep_button.grid(row=row, column=2)

        row += 1
        tk.Label(frame, text="Mode").grid(row=row, column=0)
        self.scan_mode = tk.StringVar()
        self.scan_mode.set("Discrete")
        self.scan_options = tk.OptionMenu(frame, self.scan_mode, *SCAN_OPTIONS, command=self.display_batch_entry)
        self.scan_options.grid(row=row, column=1)
        self.batch_entry = tk.Entry(frame, width=10)
        self.batch_entry.insert(10, 1)
        self.batch_entry.grid(row=row, column=2)
        self.batch_entry.config(state=tk.DISABLED)

        row += 1
        tk.Label(frame, text="DAQ Settings", font='Helvetica 16').grid(row=row, column=0, pady=10)

        row += 1
        self.goto_button = tk.Button(frame, text="Go To scanning parameter")
        self.goto_button.grid(row=row, column=0)
        self.goto_slow_button = tk.Button(frame, text="Slowly go to scanning parameter")
        self.goto_slow_button.grid(row=row, column=1)
        row += 1
        tk.Label(frame, text="Wavelength Parameter").grid(row=row, column=0)
        self.voltage_entry = tk.Entry(frame, width=10)
        self.voltage_entry.insert(10, 0)
        self.voltage_entry.grid(row=row, column=1)

        row += 1
        self.get_button = tk.Button(frame, text="Get current scanning parameter")
        self.get_button.grid(row=row, column=0)
        self.voltage_show=tk.Label(frame, text='None')
        self.voltage_show.grid(row=row, column=1)

        row += 1
        tk.Label(frame, text="Scan Limits").grid(row=row, column=0)
        self.voltage_lmin_entry = tk.Entry(frame, width=10)
        self.voltage_lmax_entry = tk.Entry(frame, width=10)
        self.voltage_lmin_entry.insert(10, float(scan_range[0]))
        self.voltage_lmax_entry.insert(10, float(scan_range[1]))
        self.voltage_lmin_entry.grid(row=row, column=1)
        self.voltage_lmax_entry.grid(row=row, column=2)

        row += 1
        tk.Label(frame, text="Hardware Configuration", font='Helvetica 16').grid(row=row, column=0, pady=10)

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

    def display_batch_entry(self, scan_mode):
        if scan_mode == "Batches":
            self.batch_entry.config(state=tk.NORMAL)
        else:
            self.batch_entry.config(state=tk.DISABLED)

    def display_downsweep_time(self):
        if self.do_downsweep.get() == 1:
            self.downsweep_time_entry.config(state=tk.NORMAL)
        else:
            self.downsweep_time_entry.config(state=tk.DISABLED)



class MainApplicationView():
    def __init__(self, main_frame, scan_range=[0, 2]) -> None:
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
        self.controller_model = None
        self.meta_configs = None
        self.app_meta_data = None
        # load the data acquisition model
        self.view.sidepanel.start_button.bind("<Button>", self.start_scan)
        self.view.sidepanel.save_scan_button.bind("<Button>", self.save_scan)
        self.view.sidepanel.stop_button.bind("<Button>", self.stop_scan)
        self.view.sidepanel.goto_button.bind("<Button>", self.go_to)
        self.view.sidepanel.goto_slow_button.bind("<Button>", self.go_to_slowly)
        self.view.sidepanel.get_button.bind("<Button>", self.update_voltage_show)
        self.view.sidepanel.hardware_config_from_yaml_button.bind("<Button>", lambda e: self.configure_from_yaml())
        self.root.protocol("WM_DELETE_WINDOWwait_visibility()", self.on_closing)

    def go_to(self, event=None) -> None:
        self.disable_buttons()
        controller_speed = self.application_controller.wavelength_controller.speed
        self.application_controller.wavelength_controller.speed = "fast"
        self.application_controller.go_to(float(self.view.sidepanel.voltage_entry.get()))
        self.application_controller.wavelength_controller.speed = controller_speed
        self.enable_buttons()

    def go_to_slowly(self, event=None) -> None:
        self.disable_buttons()
        controller_speed = self.application_controller.wavelength_controller.speed
        self.application_controller.wavelength_controller.speed = "slow"
        self.application_controller.go_to(float(self.view.sidepanel.voltage_entry.get()))
        self.application_controller.wavelength_controller.speed = controller_speed
        self.enable_buttons()

    def update_voltage_show(self, event=None) -> None:
        read = self.application_controller.wavelength_controller.last_write_value
        l = self.view.sidepanel.voltage_show
        l.config(text=read)

    def start_scan(self, event=None) -> None:
        self.disable_buttons()
        scan_mode = str(self.view.sidepanel.scan_mode.get())
        batch_size = int(self.view.sidepanel.batch_entry.get())
        n_sample_size = int(self.view.sidepanel.num_pixels.get())
        n_scans = int(self.view.sidepanel.scan_num_entry.get())
        sweep_time_entry = float(self.view.sidepanel.sweep_time_entry.get())
        do_downsweep = bool(self.view.sidepanel.do_downsweep.get())
        downsweep_time = float(self.view.sidepanel.sweep_time_entry.get())
        if not do_downsweep:
            downsweep_time_entry = None
        vstart= float(self.view.sidepanel.voltage_start_entry.get())
        vend = float(self.view.sidepanel.voltage_end_entry.get())
        step_size = (vend - vstart) / float(n_sample_size)
        args = [vstart, vend]
        args.append(step_size)
        args.append(n_sample_size)
        args.append(n_scans)
        args.append(scan_mode)
        args.append(batch_size)

        settling_time = sweep_time_entry / n_sample_size
        downsweep_settling_time = downsweep_time / n_sample_size
        self.application_controller.settling_time_in_seconds = settling_time
        self.application_controller.downsweep_settling_time_in_seconds = downsweep_settling_time

        self.app_meta_data = args
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

    def scan_thread_function(self,
                             vstart: float,
                             vend: float,
                             step_size: float,
                             n_sample_size: int,
                             n_scans: int,
                             scan_mode: str,
                             batch_size: int) -> None:
        """
        Function to be called in background thread
        Scans the voltage from vstart to vend in increments of step_size
        for a total of n_sample_size data points n_scans number of times.
        If the scan_mode is "Batches", it will aggregate (average) some
        batch_size number of points in between data points instead.
        """
        self.application_controller.set_scan_mode(scan_mode)
        self.application_controller.discrete_batch_size = batch_size
        self.application_controller.set_scan_range(vstart, vend)
        self.application_controller.step_size = step_size
        self.application_controller.tmax = n_scans
        try:
            self.application_controller.reset()  # clears the data
            self.application_controller.start()  # starts the DAQ
            self.application_controller.set_to_start()  # moves the stage to starting voltage

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
        myformats = [('Pickle', '*.pkl')]
        afile = tk.filedialog.asksaveasfilename(filetypes=myformats, defaultextension='.pkl')
        logger.info(afile)
        file_type = afile.split('.')[-1]
        if afile is None or afile == '':
            return # selection was canceled.
        data = {}
        data["Data"] = {}
        if self.application_controller is not None:
            for ii, scan_data in enumerate(self.application_controller.outputs):
                data["Data"][f"Scan{ii}"] = {}
                for reader in self.application_controller.readers:
                    data["Data"][f"Scan{ii}"][reader] = scan_data[reader]
        data["Metadata"] = []
        if self.meta_configs is not None:
            for meta_config in self.meta_configs:
                data["Metadata"].append(meta_config)
        if self.app_meta_data is not None:
            data["ApplicationController"] = self.app_meta_data

        if file_type == 'pkl':
            with open(afile, 'wb') as f:
                pickle.dump(data, f)

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
        self.meta_configs = []
        self.data_acquisition_models = {}
        if daq_readers is not None:
            for daq_reader in daq_readers:
                daq_reader_name = daq_readers[daq_reader]
                daq_reader_config = config[CONFIG_FILE_APPLICATION_NAME][daq_reader_name]
                self.meta_configs.append(daq_reader_config)
                module = importlib.import_module(daq_reader_config['import_path'])
                logger.debug(f"loading {daq_reader_config['import_path']}")
                cls = getattr(module, daq_reader_config['class_name'])
                self.data_acquisition_models[daq_reader_name] = cls(logger.level)
                self.data_acquisition_models[daq_reader_name].configure(daq_reader_config['configure'])
        wm_readers = self.app_config["readers"]["wm_readers"]
        if wm_readers is not None:
            for wm_reader in wm_readers:
                wm_reader_name = wm_readers[wm_reader]
                wm_reader_config = config[CONFIG_FILE_APPLICATION_NAME][wm_reader_name]
                self.meta_configs.append(wm_reader_config)
                module = importlib.import_module(wm_reader_config['import_path'])
                logger.debug(f"loading {wm_reader_config['import_path']}")
                cls = getattr(module, wm_reader_config['class_name'])
                self.data_acquisition_models[wm_reader_name] = cls(logger.level)
                self.data_acquisition_models[wm_reader_name].configure(wm_reader_config['configure'])
        daq_controller_name = config[CONFIG_FILE_APPLICATION_NAME]['ApplicationController']['configure']['controller']
        daq_controller_config = config[CONFIG_FILE_APPLICATION_NAME][daq_controller_name]
        self.meta_configs.append(daq_controller_config)
        if daq_controller_config is not None:
            module = importlib.import_module(daq_controller_config['import_path'])
            logger.debug(f"loading {daq_controller_config['import_path']}")
            cls = getattr(module, daq_controller_config['class_name'])
            self.controller_model = cls(logger.level)
            self.controller_model.configure(daq_controller_config['configure'])
        else:
           raise Exception("Yaml configuration file must have a controller for PLE scan.")
        self.application_controller = plescanner.PleScanner(self.data_acquisition_models, self.controller_model)

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
        self.view.sidepanel.goto_slow_button['state'] = 'disabled'
        self.view.sidepanel.controller_menu.config(state=tk.DISABLED)
        self.view.sidepanel.save_scan_button.config(state=tk.DISABLED)

    def enable_buttons(self):
        self.view.sidepanel.start_button['state'] = 'normal'
        self.view.sidepanel.goto_button['state'] = 'normal'
        self.view.sidepanel.goto_slow_button['state'] = 'normal'
        self.view.sidepanel.controller_menu.config(state=tk.NORMAL)
        self.view.sidepanel.save_scan_button.config(state=tk.NORMAL)

def main() -> None:
    tkapp = MainTkApplication(DEFAULT_DAQ_DEVICE_NAME)
    tkapp.run()


if __name__ == '__main__':
    main()

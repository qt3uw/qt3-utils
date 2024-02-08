import argparse
import tkinter as tk
import logging
from threading import Thread
import yaml
import importlib
import importlib.resources
from typing import Any, Protocol

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib
import h5py
import nidaqmx
from qt3utils.nidaq.customcontrollers import VControl
from qt3utils.datagenerators import plescanner
from qt3utils.applications.controllers.nidaqedgecounter import QT3ScopeNIDAQEdgeCounterController

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

NIDAQ_DEVICE_NAME = 'NIDAQ Rate Counter'
RANDOM_DAQ_DEVICE_NAME = 'Random Data Generator'

DEFAULT_DAQ_DEVICE_NAME = NIDAQ_DEVICE_NAME

CONTROLLER_PATH = 'qt3utils.applications.controllers'
SUPPORTED_CONTROLLERS = {NIDAQ_DEVICE_NAME: 'nidaq_rate_counter.yaml'
                         }
STANDARD_CONTROLLERS = {NIDAQ_DEVICE_NAME: {'yaml': 'nidaq_rate_counter.yaml',
                                                'application_controller_class': plescanner.CounterAndScanner}
                        }
CONFIG_FILE_APPLICATION_NAME = 'QT3PLE'
CONFIG_FILE_EXPERIMENT = 'Experiment'
CONFIG_FILE_DAQ_DEVICE = 'DAQCounter'
CONFIG_FILE_VOLTAGE_CONTROLLER = 'VoltageController'
CONFIG_FILE_DAQ_CONTROLLER = 'DAQController'

class ScanImage:
    def __init__(self, mplcolormap='gray') -> None:
        self.fig, self.ax = plt.subplots()
        self.cbar = None
        self.cmap = mplcolormap
        self.cid = self.fig.canvas.mpl_connect('button_press_event', self.onclick)
        self.ax.set_xlabel('Voltage')
        self.log_data = False

    def update(self, model) -> None:

        if self.log_data:
            data = np.log10(model.scanned_count_rate)
            data[np.isinf(data)] = 0  # protect against +-inf
        else:
            data = model.scanned_count_rate
        data = np.array(data).T.tolist()

        self.artist = self.ax.imshow(data, cmap=self.cmap, extent=[model.current_t + model.raster_line_pause,
                                                                   0,
                                                                   model.vmin,
                                                                   model.vmax + model.step_size
                                                                   ])
        if self.cbar is None:
            self.cbar = self.fig.colorbar(self.artist, ax=self.ax)
        else:
            self.cbar.update_normal(self.artist)

        if self.log_data is False:
            self.cbar.formatter.set_powerlimits((0, 3))

        self.ax.set_xlabel('Pixels')
        self.ax.set_ylabel('Voltage (V)')

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
        self.startButton = tk.Button(frame, text="Start Scan")
        self.startButton.grid(row=row, column=0)
        self.stopButton = tk.Button(frame, text="Stop Scan")
        self.stopButton.grid(row=row, column=1)
        self.saveScanButton = tk.Button(frame, text="Save Scan")
        self.saveScanButton.grid(row=row, column=2)
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
        self.v_lmin_entry.insert(10, float(scan_range[0]))
        self.v_lmax_entry.insert(10, float(scan_range[1]))
        self.v_lmin_entry.grid(row=row, column=1)
        self.v_lmax_entry.grid(row=row, column=2)

        row+=1
        self.controller_option = tk.StringVar(frame)
        self.controller_option.set(DEFAULT_DAQ_DEVICE_NAME)  # setting the default value

        self.controller_menu = tk.OptionMenu(frame,
                                             self.controller_option,
                                             *STANDARD_CONTROLLERS.keys(),
                                             command=root.load_daq_from_config_dict)
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

    #@property
    #def hardware_config_button(self) -> tk.Button:
    #    return self.sidepanel.hardware_config_button


class MainTkApplication():

    def __init__(self, controller_name) -> None:
        #self.counter_scanner = counter_scanner
        self.root = tk.Tk()
        self.view = MainApplicationView(self)
        self.view.controller_option = controller_name
        # data acquisition model that is used to acquire data
        self.data_acquisition_model = None
        # load the data acquisition model
        self.load_daq_from_config_dict(controller_name)
        self.view.sidepanel.startButton.bind("<Button>", self.start_scan)
        self.view.sidepanel.saveScanButton.bind("<Button>", self.save_scan)
        self.view.sidepanel.stopButton.bind("<Button>", self.stop_scan)
        self.view.sidepanel.GotoButton.bind("<Button>", self.go_to_voltage)
        self.view.sidepanel.hardware_config_from_yaml_button.bind("<Button>", lambda e: self.configure_from_yaml())
        self.root.protocol("WM_DELETE_WINDOWwait_visibility()", self.on_closing)

    def go_to_voltage(self, event=None) -> None:
        self.view.sidepanel.startButton['state'] = 'disabled'
        self.view.sidepanel.GotoButton['state'] = 'disabled'
        self.view.sidepanel.controller_menu.config(state=tk.DISABLED)
        self.view.sidepanel.saveScanButton.config(state=tk.DISABLED)
        self.application_controller.go_to_v(float(self.view.sidepanel.v_entry.get()))
        self.view.sidepanel.startButton['state'] = 'normal'
        self.view.sidepanel.GotoButton['state'] = 'normal'
        self.view.sidepanel.controller_menu.config(state=tk.NORMAL)
        self.view.sidepanel.saveScanButton.config(state=tk.NORMAL)

    def start_scan(self, event=None) -> None:
        self.view.sidepanel.startButton['state'] = 'disabled'
        self.view.sidepanel.GotoButton['state'] = 'disabled'
        self.view.sidepanel.controller_menu.config(state=tk.DISABLED)
        self.view.sidepanel.saveScanButton.config(state=tk.DISABLED)

        n_sample_size = int(self.view.sidepanel.num_pixels.get())
        sweep_time_entry = float(self.view.sidepanel.sweep_time_entry.get())
        vmin = float(self.view.sidepanel.v_min_entry.get())
        vmax = float(self.view.sidepanel.v_max_entry.get())
        step_size = (vmax - vmin) / float(n_sample_size)
        args = [vmin, vmax]
        args.append(step_size)
        args.append(n_sample_size)

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
        self.view.sidepanel.startButton['state'] = 'normal'
        self.view.sidepanel.GotoButton['state'] = 'normal'
        self.view.sidepanel.controller_menu.config(state=tk.NORMAL)
        self.view.sidepanel.saveScanButton.config(state=tk.NORMAL)
    def on_closing(self) -> None:
        try:
            self.stop_scan()
            self.root.quit()
            self.root.destroy()
        except Exception as e:
            logger.debug(e)
            pass

    def scan_thread_function(self, vmin, vmax, step_size, N) -> None:

        self.application_controller.set_scan_range(vmin, vmax)
        self.application_controller.step_size = step_size
        self.application_controller.set_num_data_samples_per_batch(N)

        try:
            self.application_controller.reset()  # clears the data
            self.application_controller.start()  # starts the DAQ
            self.application_controller.set_to_starting_position()  # moves the stage to starting position

            while self.application_controller.still_scanning():
                self.application_controller.scan_v()
                self.view.scan_view.update(self.application_controller)
                self.view.canvas.draw()

            self.application_controller.stop()

        except nidaqmx.errors.DaqError as e:
            logger.info(e)
            logger.info(
                'Check for other applications using resources. If not, you may need to restart the application.')

        self.view.sidepanel.startButton['state'] = 'normal'
        self.view.sidepanel.GotoButton['state'] = 'normal'
        self.view.sidepanel.controller_menu.config(state=tk.NORMAL)
        self.view.sidepanel.saveScanButton.config(state=tk.NORMAL)

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
        self.view.sidepanel.saveScanButton.config(state=tk.NORMAL)

    def configure_from_yaml(self) -> None:
        """
        This method launches a GUI window to allow the user to select a yaml file to configure the data controller.

        This does not instantiate a new hardware controller class. It only configures the existing one.
        """
        filetypes = (
            ('YAML', '*.yaml'),
        )
        afile = tk.filedialog.askopenfile(filetypes=filetypes, defaultextension='.yaml')
        if afile is None:
            return  # selection was canceled.

        config = yaml.safe_load(afile)
        afile.close()

        counter_config = config[CONFIG_FILE_APPLICATION_NAME][CONFIG_FILE_DAQ_DEVICE]

        same_daq_name = self.data_acquisition_model.__class__.__name__ == counter_config['class_name']
        same_daq_module = self.data_acquisition_model.__class__.__module__ == counter_config['import_path']

        if same_daq_name is False or same_daq_module is False:
            msg = f"""\nCurrent data acquisition object is not of type found in YAML
Found in YAML: {counter_config['import_path']}.{counter_config['class_name']}.
Current data acquistion object: {self.data_acquisition_model.__class__.__module__}.{self.data_acquisition_model.__class__.__name__}
Configuration not loaded. Please select appropriate controller from the pull-down menu
or check your YAML file to ensure configuration of supported hardware controller.
"""
            logger.warning(msg)
        else:
            logger.info("load settings from yaml")
            logger.info(counter_config['configure'])
            self.data_acquisition_model.configure(counter_config['configure'])


    def _open_config_for_hardware(self, hardware_name: str) -> dict:
        with importlib.resources.path(CONTROLLER_PATH, SUPPORTED_CONTROLLERS[hardware_name]) as yaml_path:
            logger.info(f"opening config file: {yaml_path}")
            with open(yaml_path, 'r') as yaml_file:
                config = yaml.safe_load(yaml_file)

        return config

    def load_daq_from_config_dict(self, controller_name: str) -> None:

        config = self._open_config_for_hardware(controller_name)

        counter_config = config[CONFIG_FILE_APPLICATION_NAME][CONFIG_FILE_DAQ_DEVICE]

        logger.info("loading from configuration")
        logger.info(counter_config)

        # Dynamically import the module
        module = importlib.import_module(counter_config['import_path'])

        # Dynamically instantiate the class
        cls = getattr(module, counter_config['class_name'])
        # cls should be instance of QT3ScopeNIDAQEdgeCounterController
        self.data_acquisition_model = cls(logger.level)
        assert isinstance(self.data_acquisition_model, QT3ScopeNIDAQEdgeCounterController)

        # configure the data acquisition model
        self.data_acquisition_model.configure(counter_config['configure'])
        #self.view.hardware_config_button.bind("<Button>", lambda e: self.data_acquisition_model.configure_view(self.root))
        self.animation = None  # reset the animation

    def _open_yaml_config_for_controller(self, controller_name: str) -> dict:
        with importlib.resources.path(CONTROLLER_PATH, STANDARD_CONTROLLERS[controller_name]['yaml']) as yaml_path:
            logger.info(f"opening config file: {yaml_path}")
            with open(yaml_path, 'r') as yaml_file:
                config = yaml.safe_load(yaml_file)

        return config

    def _load_controller_from_dict(self, config: dict, a_protocol: Protocol) -> Any:
        """
        Dynamically imports the module and instantiates the class specified in the config dictionary.
        Class the class configure method if it exists.
        """
        # Dynamically import the module
        module = importlib.import_module(config['import_path'])
        logger.debug(f"loading {config['import_path']}")

        # Dynamically instantiate the class
        cls = getattr(module, config['class_name'])
        logger.debug(f"instantiating {config['class_name']}")

        controller = cls(logger.level)

        logger.debug(f"asserting {config['class_name']} of proper type {a_protocol}")
        assert isinstance(controller, a_protocol)

        # configure the controller
        # all controllers *should* have a configure method
        logger.debug(f"calling {a_protocol} configure method")
        controller.configure(config['configure'])

        return controller

    def load_controller_from_name(self, application_controller_name: str) -> None:
        """
        Loads the default yaml configuration file for the application controller.

        Should be called during instantiation of this class and should be the callback
        function for the support controller pull-down menu in the side panel
        """
        logger.info(f"loading {application_controller_name}")
        config = self._open_yaml_config_for_controller(application_controller_name)
        self._build_controllers_from_config_dict(config, application_controller_name)

    def _build_controllers_from_config_dict(self, config: dict, controller_name: str) -> None:

        # load the position controller from dict
        pos_config = config[CONFIG_FILE_APPLICATION_NAME][CONFIG_FILE_VOLTAGE_CONTROLLER]
        voltage_controller = self._load_controller_from_dict(pos_config, VControl)

        # load the data acquisition model from dict
        daq_config = config[CONFIG_FILE_APPLICATION_NAME][CONFIG_FILE_DAQ_DEVICE]
        daq_controller = self._load_controller_from_dict(daq_config, QT3ScopeNIDAQEdgeCounterController)

        ControllerClass = STANDARD_CONTROLLERS[controller_name]['application_controller_class']
        self.application_controller = plescanner.CounterAndScanner(daq_controller.data_generator, voltage_controller)

        # bind buttons to controllers
        #self.view.scan_view.set_rightclick_callback(self.application_controller.scan_image_rightclick_event)
        #self.view.voltage_controller_config_button.bind("<Button>", lambda e: self.application_controller.wavelength_controller.configure_view(self.root))
        #self.view.daq_config_button.bind("<Button>", lambda e: self.application_controller.rate_counter.configure_view(self.root))
def main() -> None:
    tkapp = MainTkApplication(DEFAULT_DAQ_DEVICE_NAME)
    tkapp.run()


if __name__ == '__main__':
    main()

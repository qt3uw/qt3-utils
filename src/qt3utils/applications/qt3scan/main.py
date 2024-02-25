import argparse
import tkinter as tk
import logging
import datetime
from threading import Thread
import importlib.resources
from typing import Any, Protocol, Optional, Callable, List

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.backend_bases import MouseEvent
import matplotlib
import nidaqmx
import yaml

import qt3utils.nidaq
import qt3utils.pulsers.pulseblaster
from qt3utils.applications.qt3scan.interface import (
    QT3ScanDAQControllerInterface,
    QT3ScanPositionControllerInterface,
    QT3ScanApplicationControllerInterface,
)
from qt3utils.applications.qt3scan.controller import (
    QT3ScanConfocalApplicationController,
    QT3ScanHyperSpectralApplicationController
)

matplotlib.use('Agg')


parser = argparse.ArgumentParser(description='QT3Scan', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('-v', '--verbose', type=int, default=2, help='0 = quiet, 1 = info, 2 = debug.')
args = parser.parse_args()

logger = logging.getLogger(__name__)
logging.basicConfig()

if args.verbose == 0:
    logger.setLevel(logging.WARNING)
if args.verbose == 1:
    logger.setLevel(logging.INFO)
if args.verbose == 2:
    logger.setLevel(logging.DEBUG)


NIDAQ_DAQ_DEVICE_NAME = 'NIDAQ Edge Counter'
RANDOM_DATA_DAQ_DEVICE_NAME = 'Random Counter'
PRINCETON_SPECTROMETER_DAQ_DEVICE_NAME = 'Princeton Spectrometer'
RANDOM_SPECTROMETER_DAQ_DEVICE_NAME = 'Random Spectrometer'

DEFAULT_DAQ_DEVICE_NAME = NIDAQ_DAQ_DEVICE_NAME

CONTROLLER_PATH = 'qt3utils.applications.controllers'
STANDARD_CONTROLLERS = {NIDAQ_DAQ_DEVICE_NAME: {'yaml': 'nidaq_edge_counter.yaml',
                        'application_controller_class': QT3ScanConfocalApplicationController},
                        PRINCETON_SPECTROMETER_DAQ_DEVICE_NAME: {'yaml': 'princeton_spectrometer.yaml',
                        'application_controller_class': QT3ScanHyperSpectralApplicationController},
                        RANDOM_DATA_DAQ_DEVICE_NAME: {'yaml': 'random_data_generator.yaml',
                        'application_controller_class': QT3ScanConfocalApplicationController},
                        RANDOM_SPECTROMETER_DAQ_DEVICE_NAME: {'yaml': 'random_spectrometer.yaml',
                        'application_controller_class': QT3ScanHyperSpectralApplicationController}
                        }

# Hyper Spectral Imaging would add the following to STANDARD_CONTROLLERS
# PRINCETON_SPECTROMETER_DAQ_DEVICE_NAME = 'Princeton Spectrometer'
# PRINCETON_SPECTROMETER_DAQ_DEVICE_NAME: {'yaml':'princeton_spectromter.yaml',
#                           'application_controller_class': QT3ScanHyperSpectralApplicationController}

CONFIG_FILE_APPLICATION_NAME = 'QT3Scan'
CONFIG_FILE_POSITION_CONTROLLER = 'PositionController'
CONFIG_FILE_DAQ_CONTROLLER = 'DAQController'


class ScanImage:
    def __init__(self, mplcolormap: str = 'gray'):
        self.fig, self.ax = plt.subplots()
        self.cbar = None
        self.cmap = mplcolormap
        self.fig.canvas.mpl_connect('button_press_event', self.onclick)
        self.ax.set_xlabel('x position (um)')
        self.ax.set_ylabel('y position (um)')
        self.log_data = False
        self.pointer_line2d = None
        self.position_line2d = None
        self.app_controller_step_size = 0
        self.xmin = None
        self.ymin = None

    def update(self, app_controller: QT3ScanApplicationControllerInterface) -> None:

        if len(app_controller.scanned_count_rate) == 0:
            return

        if self.log_data:
            data = np.log10(app_controller.scanned_count_rate)
            data[np.isinf(data)] = 0  # protect against +-inf
        else:
            data = app_controller.scanned_count_rate

        # we must retain these values for callback functions (feels a bit hacky)
        self.app_controller_step_size = app_controller.step_size
        self.xmin = app_controller.xmin
        self.ymin = app_controller.ymin

        # shift the extent so that position centers are directly aligned with data
        # rather than aligned on bin edges
        self.artist = self.ax.imshow(data, origin='lower',
                                     cmap=self.cmap,
                                     extent=[app_controller.xmin - app_controller.step_size / 2.0,
                                             app_controller.xmax - app_controller.step_size / 2.0,
                                             app_controller.ymin - app_controller.step_size / 2.0,
                                             app_controller.current_y - app_controller.step_size / 2.0])

        if self.cbar is None:
            self.cbar = self.fig.colorbar(self.artist, ax=self.ax)
        else:
            self.cbar.update_normal(self.artist)

        if self.log_data is False:
            self.cbar.formatter.set_powerlimits((0, 3))

        self.ax.set_xlabel('x position (um)')
        self.ax.set_ylabel('y position (um)')

    def reset(self) -> None:
        self.ax.cla()
        self.pointer_line2d = None
        self.position_line2d = None
        self.app_controller_step_size = 0
        self.xmin = None
        self.ymin = None

    def set_onclick_callback(self, func: Callable) -> None:
        """
        The callback function should expect three arguments
            * matplotlib.backend_bases.MouseEvent
            * pixel_x
            * pixel_y

            where pixel_x and pixel_y correspond to the pixel
            index of the data
        """
        self.onclick_callback = func

    def set_rightclick_callback(self, func: Callable) -> None:
        """
        The callback function should expect three arguments
            * matplotlib.backend_bases.MouseEvent
            * pixel_x
            * pixel_y

            where pixel_x and pixel_y correspond to the pixel
            index of the data
        """
        self.rightclick_callback = func

    def update_pointer_indicator(self, x_position: float, y_position: float) -> None:
        """
        Updates the pointer marker on the scan image to show a proposed new position on the image.
        """
        if self.pointer_line2d is not None:
            self.pointer_line2d[0].set_data([[x_position], [y_position]])
        else:
            self.pointer_line2d = self.ax.plot(x_position, y_position, 'yx', label='pointer')

    def update_position_indicator(self, x_position: float, y_position: float) -> None:
        """
        Updates the position marker on the scan image to show the current position on the image.
        """
        if self.position_line2d is not None:
            self.position_line2d[0].set_data([[x_position], [y_position]])
        else:
            self.position_line2d = self.ax.plot(x_position, y_position, 'ro', label='pos')

    def onclick(self, event: MouseEvent) -> None:
        if event.inaxes != self.ax:
            return

        logger.debug(f"Button {event.button} click at: ({event.xdata} microns, {event.ydata}) microns")

        if event.xdata is None or event.ydata is None:
            logger.debug("Button click outside of scan")
            return
        if self.xmin is None or self.ymin is None:
            logger.debug("No data to display")
            return

        dist_x = event.xdata + self.app_controller_step_size / 2 - self.xmin  # we have to subtract step_size / 2 because the GUI shifts the view.
        dist_y = event.ydata + self.app_controller_step_size / 2 - self.ymin
        logger.debug(f'Selected position at distance from lower left (x, y): {dist_x, dist_y}')
        index_x = int(dist_x / self.app_controller_step_size)
        index_y = int(dist_y / self.app_controller_step_size)

        if event.button == 3:  # Right click
            self.rightclick_callback(event, index_x, index_y)
        elif event.button == 1:  # Left click
            self.onclick_callback(event, index_x, index_y)
            self.update_pointer_indicator(event.xdata, event.ydata)
            self.fig.canvas.draw()


class SidePanel():
    def __init__(self, application):
        frame = tk.Frame(application.root_window)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        row = 0
        tk.Label(frame, text="Scan Settings", font='Helvetica 16').grid(row=row, column=0, pady=10)
        row += 1
        tk.Label(frame, text="x range (um)").grid(row=row, column=0)
        self.x_min_entry = tk.Entry(frame, width=10)
        self.x_max_entry = tk.Entry(frame, width=10)
        self.x_min_entry.grid(row=row, column=1)
        self.x_max_entry.grid(row=row, column=2)

        row += 1
        tk.Label(frame, text="y range (um)").grid(row=row, column=0)
        self.y_min_entry = tk.Entry(frame, width=10)
        self.y_max_entry = tk.Entry(frame, width=10)
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
        tk.Label(frame, text="DAQ Settings", font='Helvetica 16').grid(row=row, column=0, pady=10)

        row += 1
        self.controller_option = tk.StringVar(frame)
        self.controller_option.set(DEFAULT_DAQ_DEVICE_NAME)
        # todo - TkOptionMenu doesn't have a way, that I know of,
        # to modify the callback after instantiation. Therefore,
        # for now, we need to pass the app_controller to this class
        # so that it can be used in the callback when a hardware option is selected.
        self.controller_menu = tk.OptionMenu(frame,
                                             self.controller_option,
                                             *STANDARD_CONTROLLERS.keys(),
                                             command=application.load_controller_from_name)
        self.controller_menu.grid(row=row, column=0, columnspan=3)

        row += 1
        self.daq_config_button = tk.Button(frame, text="Data Acquisition Config")
        self.daq_config_button.grid(row=row, column=0, columnspan=3)

        row += 1
        self.position_controller_config_button = tk.Button(frame, text="Position Controller Config")
        self.position_controller_config_button.grid(row=row, column=0, columnspan=3)

        row += 1
        self.config_from_yaml_button = tk.Button(frame, text="Load YAML Config")
        self.config_from_yaml_button.grid(row=row, column=0, columnspan=3)

        # todo -- package view settings into a separate GUI breakout window
        row += 1
        tk.Label(frame, text="View Settings", font='Helvetica 16').grid(row=row, column=0, pady=10)
        row += 1
        self.set_color_map_button = tk.Button(frame, text="Set Color")
        self.set_color_map_button.grid(row=row, column=0, pady=(2, 15))
        self.mpl_color_map_entry = tk.Entry(frame, width=10)
        self.mpl_color_map_entry.insert(10, 'gray')
        self.mpl_color_map_entry.grid(row=row, column=1, pady=(2, 15))

        self.log10Button = tk.Button(frame, text="Log10")
        self.log10Button.grid(row=row, column=2, pady=(2, 15))

    def update_go_to_position(self,
                              x: Optional[float] = None,
                              y: Optional[float] = None,
                              z: Optional[float] = None) -> None:
        if x is not None:
            self.go_to_x_position_text.set(np.round(x, 4))
        if y is not None:
            self.go_to_y_position_text.set(np.round(y, 4))
        if z is not None:
            self.z_entry_text.set(np.round(z, 4))

    def mpl_onclick_callback(self, mpl_event: MouseEvent, index_x: int, index_y: int) -> None:
        if mpl_event.xdata and mpl_event.ydata:
            self.update_go_to_position(mpl_event.xdata, mpl_event.ydata)

    def set_scan_range(self, scan_range: List[float]) -> None:
        self.x_min_entry.insert(10, scan_range[0])
        self.x_max_entry.insert(10, scan_range[1])
        self.y_min_entry.insert(10, scan_range[0])
        self.y_max_entry.insert(10, scan_range[1])


class MainApplicationView():
    def __init__(self, application):
        frame = tk.Frame(application.root_window)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scan_view = ScanImage()
        self.sidepanel = SidePanel(application)
        self.scan_view.set_onclick_callback(self.sidepanel.mpl_onclick_callback)

        self.canvas = FigureCanvasTkAgg(self.scan_view.fig, master=frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(self.canvas, frame)
        toolbar.update()
        self.canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.canvas.draw()

    @property
    def controller_menu(self) -> tk.OptionMenu:
        return self.sidepanel.controller_menu

    @property
    def controller_option(self) -> tk.StringVar:
        return self.sidepanel.controller_option

    @controller_option.setter
    def controller_option(self, value):
        self.sidepanel.controller_option.set(value)

    @property
    def daq_config_button(self) -> tk.Button:
        return self.sidepanel.daq_config_button

    @property
    def position_controller_config_button(self) -> tk.Button:
        return self.sidepanel.position_controller_config_button

    @property
    def config_from_yaml_button(self) -> tk.Button:
        return self.sidepanel.config_from_yaml_button

    def set_scan_range(self, scan_range: List[float]) -> None:
        self.sidepanel.set_scan_range(scan_range)

    def show_optimization_plot(self, title: str,
                               old_opt_value: float,
                               new_opt_value: float,
                               x_vals: np.ndarray,
                               y_vals: np.ndarray,
                               fit_coeff: np.ndarray = None) -> None:
        """
        Consturcts a new window with a plot of the optimization data.

        title: title of the window
        old_opt_value: the old optimized value
        new_opt_value: the new optimized value
        x_vals: the x values of the data
        y_vals: the measured y values of the data
        fit_coeff: the fit coefficients of the function qt3utils.datagenerators.piezoscanner.gauss
        """
        win = tk.Toplevel()
        win.title(title)
        fig, ax = plt.subplots()
        ax.set_xlabel('position (um)')
        ax.set_ylabel('count rate (Hz)')
        ax.plot(x_vals, y_vals, label='data')
        ax.ticklabel_format(style='sci', scilimits=(0, 3))
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

    def __init__(self, application_controller_name: str):
        self.root_window = tk.Tk()

        self.view = MainApplicationView(self)
        self.view.controller_option = application_controller_name

        self.view.sidepanel.startButton.bind("<Button>", lambda e: self.start_scan())
        self.view.sidepanel.stopButton.bind("<Button>", lambda e: self.stop_scan())
        self.view.sidepanel.log10Button.bind("<Button>", lambda e: self.log_scan_image())
        self.view.sidepanel.gotoButton.bind("<Button>", lambda e: self.go_to_position())
        self.view.sidepanel.go_to_z_button.bind("<Button>", lambda e: self.go_to_z())
        self.view.sidepanel.saveScanButton.bind("<Button>", lambda e: self.save_scan())
        self.view.sidepanel.popOutScanButton.bind("<Button>", lambda e: self.pop_out_scan())

        self.view.sidepanel.set_color_map_button.bind("<Button>", lambda e: self.set_color_map())

        self.view.sidepanel.optimize_x_button.bind("<Button>", lambda e: self.optimize('x'))
        self.view.sidepanel.optimize_y_button.bind("<Button>", lambda e: self.optimize('y'))
        self.view.sidepanel.optimize_z_button.bind("<Button>", lambda e: self.optimize('z'))
        self.view.config_from_yaml_button.bind("<Button>", lambda e: self.configure_from_yaml())

        self.load_controller_from_name(application_controller_name)

        scan_range = [self.application_controller.position_controller.minimum_allowed_position,
                      self.application_controller.position_controller.maximum_allowed_position]

        self.view.set_scan_range(scan_range)

        self.root_window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.scan_thread = None

        self.optimized_position = {'x': 0, 'y': 0, 'z': -1}
        self.optimized_position['z'] = self.application_controller.position_controller.get_current_position()[2]
        self.optimized_position['z'] = self.optimized_position['z'] if self.optimized_position['z'] is not None else 0  # protects against None value returned by position controller when it cannot connect to hardware
        self.view.sidepanel.z_entry_text.set(np.round(self.optimized_position['z'], 4))

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
        pos_config = config[CONFIG_FILE_APPLICATION_NAME][CONFIG_FILE_POSITION_CONTROLLER]
        position_controller = self._load_controller_from_dict(pos_config, QT3ScanPositionControllerInterface)

        # load the data acquisition model from dict
        daq_config = config[CONFIG_FILE_APPLICATION_NAME][CONFIG_FILE_DAQ_CONTROLLER]
        daq_controller = self._load_controller_from_dict(daq_config, QT3ScanDAQControllerInterface)

        ControllerClass = STANDARD_CONTROLLERS[controller_name]['application_controller_class']
        self.application_controller = ControllerClass(position_controller, daq_controller, logger.level)

        # bind buttons to controllers
        self.view.scan_view.set_rightclick_callback(self.application_controller.scan_image_rightclick_event)
        self.view.position_controller_config_button.bind("<Button>", lambda e: self.application_controller.position_controller.configure_view(self.root_window))
        self.view.daq_config_button.bind("<Button>", lambda e: self.application_controller.daq_controller.configure_view(self.root_window))

    def configure_from_yaml(self) -> None:
        """
        This method launches a GUI window to allow the user to select a yaml file to configure the data controller.

        This does instantiate a new hardware controller classes and calls configure.
        """
        filetypes = (
            ('YAML', '*.yaml'),
        )
        afile = tk.filedialog.askopenfile(filetypes=filetypes, defaultextension='.yaml')
        if afile is None:
            return  # selection was canceled.

        config = yaml.safe_load(afile)
        afile.close()

        self._build_controllers_from_config_dict(config, self.view.controller_option.get())

    def run(self) -> None:
        self.root_window.title("QT3Scan: Piezo Controlled NIDAQ Digital Count Rate Scanner")
        self.root_window.deiconify()
        self.root_window.mainloop()

    def go_to_position(self) -> None:

        x = self.view.sidepanel.go_to_x_position_text.get()
        y = self.view.sidepanel.go_to_y_position_text.get()
        self.application_controller.position_controller.go_to_position(x, y)
        self.optimized_position['x'] = x
        self.optimized_position['y'] = y
        self.view.scan_view.update_position_indicator(x, y)

        if len(self.application_controller.scanned_count_rate) > 0:
            self.view.scan_view.update(self.application_controller)
            self.view.canvas.draw()

    def go_to_z(self) -> None:
        self.application_controller.position_controller.go_to_position(z=self.view.sidepanel.z_entry_text.get())
        self.optimized_position['z'] = self.view.sidepanel.z_entry_text.get()

    def set_color_map(self) -> None:
        proposed_cmap = self.view.sidepanel.mpl_color_map_entry.get()
        if proposed_cmap in plt.colormaps():
            self.view.scan_view.cmap = proposed_cmap
        else:
            logger.error(f"Color map {proposed_cmap} not found in matplotlib colormaps:")
            logger.error(f'{plt.colormaps()}')
        if self.application_controller.still_scanning() is False:
            self.view.scan_view.update(self.application_controller)
            self.view.canvas.draw()

    def log_scan_image(self) -> None:
        self.view.scan_view.log_data = not self.view.scan_view.log_data
        if self.application_controller.still_scanning() is False:
            self.view.scan_view.update(self.application_controller)
            self.view.canvas.draw()

    def stop_scan(self) -> None:
        self.application_controller.stop()

    def pop_out_scan(self) -> None:
        """
        Creates a new TKinter window with the data from the current scan. This allows researchers
        to retain scan image in a separate window and run subsequent scans.
        """

        win = tk.Toplevel()
        win.title(f'Scan {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

        new_scan_view = ScanImage(self.view.scan_view.cmap)
        new_scan_view.update(self.application_controller)

        canvas = FigureCanvasTkAgg(new_scan_view.fig, master=win)
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(canvas, win)
        toolbar.update()
        canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        canvas.draw()

    def _scan_thread_function(self, xmin: float, xmax: float, ymin: float, ymax: float, step_size: float) -> None:

        try:
            self.application_controller.set_scan_range(xmin, xmax, ymin, ymax)
            self.application_controller.step_size = step_size
            self.application_controller.reset()  # clears the data
            self.application_controller.start()  # starts the DAQ
            self.application_controller.set_to_starting_position()  # moves the stage to starting position

            while self.application_controller.still_scanning():
                self.application_controller.scan_x()
                self.application_controller.move_y()
                self.view.scan_view.update(self.application_controller)
                self.view.canvas.draw()

            self.application_controller.stop()

        except nidaqmx.errors.DaqError as e:
            logger.warning(e)
            logger.warning('Check for other applications using resources.')
        except ValueError as e:
            logger.warning(e)
            logger.warning('Check your configurtion! You may have entered a value that is out of range')

        finally:
            self.view.sidepanel.startButton.config(state=tk.NORMAL)
            self.view.sidepanel.go_to_z_button.config(state=tk.NORMAL)
            self.view.sidepanel.gotoButton.config(state=tk.NORMAL)
            self.view.sidepanel.saveScanButton.config(state=tk.NORMAL)
            self.view.sidepanel.popOutScanButton.config(state=tk.NORMAL)

            self.view.sidepanel.optimize_x_button.config(state=tk.NORMAL)
            self.view.sidepanel.optimize_y_button.config(state=tk.NORMAL)
            self.view.sidepanel.optimize_z_button.config(state=tk.NORMAL)

            self.view.sidepanel.controller_menu.config(state=tk.NORMAL)
            self.view.sidepanel.daq_config_button.config(state=tk.NORMAL)
            self.view.sidepanel.position_controller_config_button.config(state=tk.NORMAL)
            self.view.sidepanel.config_from_yaml_button.config(state=tk.NORMAL)

    def start_scan(self) -> None:
        self.view.sidepanel.startButton.config(state=tk.DISABLED)
        self.view.sidepanel.go_to_z_button.config(state=tk.DISABLED)
        self.view.sidepanel.gotoButton.config(state=tk.DISABLED)
        self.view.sidepanel.saveScanButton.config(state=tk.DISABLED)
        self.view.sidepanel.popOutScanButton.config(state=tk.DISABLED)

        self.view.sidepanel.optimize_x_button.config(state=tk.DISABLED)
        self.view.sidepanel.optimize_y_button.config(state=tk.DISABLED)
        self.view.sidepanel.optimize_z_button.config(state=tk.DISABLED)

        self.view.sidepanel.controller_menu.config(state=tk.DISABLED)
        self.view.sidepanel.daq_config_button.config(state=tk.DISABLED)
        self.view.sidepanel.position_controller_config_button.config(state=tk.DISABLED)
        self.view.sidepanel.config_from_yaml_button.config(state=tk.DISABLED)

        # clear the figure
        self.view.scan_view.reset()

        # get the scan settings
        xmin = float(self.view.sidepanel.x_min_entry.get())
        xmax = float(self.view.sidepanel.x_max_entry.get())
        ymin = float(self.view.sidepanel.y_min_entry.get())
        ymax = float(self.view.sidepanel.y_max_entry.get())

        args = [xmin, xmax, ymin, ymax]
        args.append(float(self.view.sidepanel.step_size_entry.get()))

        # get this value from the DAQ controller
        self.scan_thread = Thread(target=self._scan_thread_function,
                                  args=args)
        self.scan_thread.start()

    def save_scan(self) -> None:
        afile = tk.filedialog.asksaveasfilename(filetypes=self.application_controller.allowed_file_save_formats(),
                                                defaultextension=self.application_controller.default_file_format())
        if afile is None or afile == '':
            return  # selection was canceled.

        logger.info(f'Saving data to {afile}')
        self.application_controller.save_scan(afile)

    def _optimize_thread_function(self, axis: str, central: float, range: float, step_size: float) -> None:
        '''
        This function is called by the optimize function. It is not intended to be called directly.
        '''

        try:
            data, axis_vals, opt_pos, coeff = self.application_controller.optimize_position(axis,
                                                                                            central,
                                                                                            range,
                                                                                            step_size)
            self.optimized_position[axis] = opt_pos
            self.application_controller.position_controller.go_to_position(**{axis: opt_pos})
            self.view.show_optimization_plot(f'Optimize {axis}',
                                             central,
                                             self.optimized_position[axis],
                                             axis_vals,
                                             data,
                                             coeff)
            self.view.sidepanel.update_go_to_position(**{axis: self.optimized_position[axis]})
            self.view.scan_view.update_position_indicator(self.optimized_position['x'],
                                                          self.optimized_position['y'])
            self.view.canvas.draw()

        except nidaqmx.errors.DaqError as e:
            logger.info(e)
            logger.info('Check for other applications using resources. If not, you may need to restart the application.')

        except NotImplementedError as e:
            logger.info(e)

        finally:
            self.view.sidepanel.startButton.config(state=tk.NORMAL)
            self.view.sidepanel.stopButton.config(state=tk.NORMAL)
            self.view.sidepanel.go_to_z_button.config(state=tk.NORMAL)
            self.view.sidepanel.gotoButton.config(state=tk.NORMAL)
            self.view.sidepanel.saveScanButton.config(state=tk.NORMAL)
            self.view.sidepanel.popOutScanButton.config(state=tk.NORMAL)

            self.view.sidepanel.optimize_x_button.config(state=tk.NORMAL)
            self.view.sidepanel.optimize_y_button.config(state=tk.NORMAL)
            self.view.sidepanel.optimize_z_button.config(state=tk.NORMAL)

            self.view.sidepanel.controller_menu.config(state=tk.NORMAL)
            self.view.sidepanel.daq_config_button.config(state=tk.NORMAL)
            self.view.sidepanel.position_controller_config_button.config(state=tk.NORMAL)
            self.view.sidepanel.config_from_yaml_button.config(state=tk.NORMAL)

    def optimize(self, axis: str) -> None:

        opt_range = float(self.view.sidepanel.optimize_range_entry.get())
        opt_step_size = float(self.view.sidepanel.optimize_step_size_entry.get())
        old_optimized_value = self.optimized_position[axis]

        self.view.sidepanel.startButton.config(state=tk.DISABLED)
        self.view.sidepanel.stopButton.config(state=tk.DISABLED)
        self.view.sidepanel.go_to_z_button.config(state=tk.DISABLED)
        self.view.sidepanel.gotoButton.config(state=tk.DISABLED)
        self.view.sidepanel.saveScanButton.config(state=tk.DISABLED)
        self.view.sidepanel.popOutScanButton.config(state=tk.DISABLED)

        self.view.sidepanel.optimize_x_button.config(state=tk.DISABLED)
        self.view.sidepanel.optimize_y_button.config(state=tk.DISABLED)
        self.view.sidepanel.optimize_z_button.config(state=tk.DISABLED)

        self.view.sidepanel.controller_menu.config(state=tk.DISABLED)
        self.view.sidepanel.daq_config_button.config(state=tk.DISABLED)
        self.view.sidepanel.position_controller_config_button.config(state=tk.DISABLED)
        self.view.sidepanel.config_from_yaml_button.config(state=tk.DISABLED)

        self.optimize_thread = Thread(target=self._optimize_thread_function,
                                      args=(axis, old_optimized_value, opt_range, opt_step_size))
        self.optimize_thread.start()

    def on_closing(self) -> None:
        try:
            self.stop_scan()
        except Exception as e:
            logger.debug(e)
        finally:
            self.root_window.quit()
            self.root_window.destroy()


def main():
    tkapp = MainTkApplication(DEFAULT_DAQ_DEVICE_NAME)
    tkapp.run()


if __name__ == '__main__':
    main()

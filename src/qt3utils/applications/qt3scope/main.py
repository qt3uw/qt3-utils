import argparse
import collections
import tkinter as Tk
import logging
import yaml
import importlib
import importlib.resources
from typing import Optional, Tuple

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from qt3utils.applications.qt3scope.interface import QT3ScopeDAQControllerInterface

logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description='Digital input terminal rate counter.',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

# TODO -- eventually move this to adjustable option in GUI
parser.add_argument('-w', '--scope-width', metavar='width', default=500, type=int,
                    help='Number of measurements to display in window.')
# TODO -- eventually move this to adjustable option in GUI
parser.add_argument('-aut', '--animation-update-interval', metavar='milliseconds', default=20,
                    help='''Sets the animation update period, t, (in milliseconds).
                    This is the time delay between calls to acquire new data.
                    You should be limited by the data acquisition time = N / clock_rate.''')
parser.add_argument('-v', '--verbose', type=int, default=1,
                    help='verbose = 0 sets to quiet, 1 sets to info, 2 sets to debug".')

args = parser.parse_args()

logging.basicConfig()

if args.verbose == 0:
    logger.setLevel(logging.WARNING)
if args.verbose == 1:
    logger.setLevel(logging.INFO)
if args.verbose == 2:
    logger.setLevel(logging.DEBUG)

NIDAQ_DEVICE_NAME = 'NIDAQ Edge Counter'
RANDOM_DAQ_DEVICE_NAME = 'Random Data Generator'

DEFAULT_DAQ_DEVICE_NAME = NIDAQ_DEVICE_NAME

CONTROLLER_PATH = 'qt3utils.applications.controllers'
SUPPORTED_CONTROLLERS = {NIDAQ_DEVICE_NAME: 'nidaq_edge_counter.yaml',
                         RANDOM_DAQ_DEVICE_NAME: 'random_data_generator.yaml',
                         }
CONFIG_FILE_APPLICATION_NAME = 'QT3Scope'
CONFIG_FILE_DAQ_DEVICE = 'DAQController'


class ScopeFigure:

    def __init__(self, width: int = 50,
                 fig: Optional[plt.Figure] = None,
                 ax: Optional[plt.Axes] = None):
        if ax is None:
            fig, ax = plt.subplots(figsize=(6, 4))
            self._fig = fig
            self.ax = ax
        else:
            self._fig = fig
            self.ax = ax

        self.width = width
        self.reset()

        self.line, = self.ax.plot(self.ydata)
        self.ax.set_ylabel('counts / sec')
        self.ax.ticklabel_format(style='sci', scilimits=(-3, 4), axis='y')

    def init(self) -> Tuple[plt.Line2D]:
        """
        This method is used to initialize the Line2D object.
        Pass this to the animation.FuncAnimation init_func argument.
        """
        self.line.set_ydata(self.ydata)
        return (self.line,)

    def reset(self, width: Optional[int] = None) -> None:
        """
        This method is used to reset the data in ScopeFigure.
        """
        if width is None:
            width = self.width
        self.ydata = collections.deque(np.zeros(width))

    def update(self, y: float) -> Tuple[plt.Line2D]:
        """
        This method is used to update the data in ScopeFigure.
        Args:
            y: float value to append to the data.

        Pass this to the animation.FuncAnimation func argument.

        Returns:
            Tuple(plt.Line2D)
        """
        self.ydata.popleft()
        self.ydata.append(y)

        delta = 0.1*np.max(self.ydata)
        new_min = np.max([0, np.min(self.ydata) - delta])
        new_max = np.max(self.ydata) + delta
        current_min, current_max = self.ax.get_ylim()
        if (np.abs((new_min - current_min)/(current_min)) > 0.12) or (np.abs((new_max - current_max)/(current_max)) > 0.12):
            self.ax.set_ylim(np.max([0.01, np.min(self.ydata) - delta]), np.max(self.ydata) + delta)
        self.line.set_ydata(self.ydata)
        return (self.line,)

    @property
    def fig(self) -> plt.Figure:
        return self._fig


class MainApplicationView():
    def __init__(self, app_controller):
        """
        app_controller must be an instance of MainTkApplication
        """

        # there are two frames in the main window
        # the scope frame on the left and the side panel on the right

        # create, configure and place the scope frame
        scope_frame = Tk.Frame(app_controller.root_window)

        self._scope = ScopeFigure(args.scope_width)
        self.canvas = FigureCanvasTkAgg(self.scope.fig, master=scope_frame)
        self.canvas.get_tk_widget().pack(side=Tk.TOP, fill=Tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(self.canvas, scope_frame)
        toolbar.update()
        self.canvas._tkcanvas.pack(side=Tk.TOP, fill=Tk.BOTH, expand=True)
        self.canvas.draw()

        scope_frame.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=True)

        # create and place the side panel
        self.sidepanel = SidePanel(app_controller)
        self.sidepanel.frame.pack(side=Tk.RIGHT, fill=Tk.BOTH, expand=True)

    @property
    def scope(self) -> ScopeFigure:
        return self._scope

    @property
    def start_button(self) -> Tk.Button:
        return self.sidepanel.startButton

    @property
    def stop_button(self) -> Tk.Button:
        return self.sidepanel.stopButton

    @property
    def controller_option(self) -> str:
        return self.sidepanel.controller_option.get()

    @controller_option.setter
    def controller_option(self, value: str):
        self.sidepanel.controller_option.set(value)

    @property
    def hardware_config_button(self) -> Tk.Button:
        return self.sidepanel.hardware_config_button

    @property
    def hardware_config_from_yaml_button(self) -> Tk.Button:
        return self.sidepanel.hardware_config_from_yaml_button

    @property
    def controller_menu(self) -> Tk.OptionMenu:
        return self.sidepanel.controller_menu

    def reset_scope(self) -> None:
        self.scope.reset()
        self.canvas.draw_idle()


class SidePanel():
    def __init__(self, app_controller):
        """
        app_controller must be an instance of MainTkApplication
        """
        self._frame = Tk.Frame(app_controller.root_window, width=100)

        self.startButton = Tk.Button(self.frame, text="Start ")
        self.startButton.pack(side="top", fill=Tk.BOTH)

        self.stopButton = Tk.Button(self.frame, text="Stop")
        self.stopButton.pack(side="top", fill=Tk.BOTH)

        self.controller_option = Tk.StringVar(self.frame)
        self.controller_option.set(DEFAULT_DAQ_DEVICE_NAME)  # setting the default value

        # todo - TkOptionMenu doesn't have a way, that I know of,
        # to modify the callback after instantiation. Therefore,
        # for now, we need to pass the app_controller to this class
        # so that it can be used in the callback when a hardware option is selected.
        self.controller_menu = Tk.OptionMenu(self.frame,
                                             self.controller_option,
                                             *SUPPORTED_CONTROLLERS.keys(),
                                             command=app_controller.load_daq_from_config_dict)

        self.controller_menu.pack(side="top", fill=Tk.BOTH)

        self.hardware_config_button = Tk.Button(self.frame, text="Configure Hardware")
        self.hardware_config_button.pack(side="top", fill=Tk.BOTH)

        self.hardware_config_from_yaml_button = Tk.Button(self.frame, text="Load YAML Config")
        self.hardware_config_from_yaml_button.pack(side="top", fill=Tk.BOTH)

    @property
    def frame(self) -> Tk.Frame:
        return self._frame


class MainTkApplication():

    def __init__(self, controller_name: str):
        """
        controller_name must be one of SUPPORTED_CONTROLLERS.keys()
        """

        self._root_window = Tk.Tk()
        self.view = MainApplicationView(self)

        self.view.controller_option = controller_name

        # data acquisition model that is used to acquire data
        self.data_acquisition_model = None
        # load the data acquisition model
        self.load_daq_from_config_dict(controller_name)

        self.root_window.protocol("WM_DELETE_WINDOW", self._on_closing)

        self.view.start_button.bind("<Button>", lambda e: self.start_scope())
        self.view.stop_button.bind("<Button>", lambda e: self.stop_scope())
        self.view.hardware_config_from_yaml_button.bind("<Button>", lambda e: self.configure_from_yaml())

        self.animation = None

    @property
    def root_window(self) -> Tk.Tk:
        return self._root_window

    def run(self) -> None:
        """
        This method is used to run the GUI.
        """
        logger.debug('run')
        self.root_window.title("QT3Scope: NIDAQ Digital Input Count Rate")
        self.root_window.deiconify()
        self.root_window.mainloop()

    def stop_scope(self) -> None:
        logger.debug('stop_scope')
        try:
            self.data_acquisition_model.stop()
        except Exception as e:
            logger.warning(e)

        if self.animation is not None:
            self.animation.pause()

        self.view.start_button.config(state=Tk.NORMAL)
        self.view.stop_button.config(state=Tk.NORMAL)
        self.view.controller_menu.config(state=Tk.NORMAL)
        self.view.hardware_config_button.config(state=Tk.NORMAL)
        self.view.hardware_config_from_yaml_button.config(state=Tk.NORMAL)

    def start_scope(self) -> None:
        logger.debug('start_scope')
        if self.animation is None:
            self.view.canvas.draw_idle()
            self.animation = animation.FuncAnimation(self.view.scope.fig,
                                                     self.view.scope.update,
                                                     self.data_acquisition_model.yield_count_rate,
                                                     init_func=self.view.scope.init,
                                                     interval=args.animation_update_interval,
                                                     blit=False,
                                                     cache_frame_data=False)
        try:
            self.data_acquisition_model.start()
            self.animation.resume()
            self.view.start_button.config(state=Tk.DISABLED)
            self.view.stop_button.config(state=Tk.NORMAL)
            self.view.controller_menu.config(state=Tk.DISABLED)
            self.view.hardware_config_button.config(state=Tk.DISABLED)
            self.view.hardware_config_from_yaml_button.config(state=Tk.DISABLED)

        except Exception as e:
            logger.error(e)
            self.stop_scope()

    def _on_closing(self) -> None:
        logger.debug('_on_closing')
        try:
            self.stop_scope()
            self.data_acquisition_model.close()
            self.root_window.quit()
            self.root_window.destroy()
        except Exception as e:
            logger.warning(e)
            pass

    def configure_from_yaml(self) -> None:
        """
        This method launches a GUI window to allow the user to select a yaml file to configure the data controller.

        This does not instantiate a new hardware controller class. It only configures the existing one.
        """
        filetypes = (
            ('YAML', '*.yaml'),
        )
        afile = Tk.filedialog.askopenfile(filetypes=filetypes, defaultextension='.yaml')
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
Configuration not loaded. Please select approprate controller from the pull-down menu
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
        # cls should be instance of QT3ScopeDAQControllerInterface
        self.data_acquisition_model = cls(logger.level)
        assert isinstance(self.data_acquisition_model, QT3ScopeDAQControllerInterface)

        # configure the data acquisition model
        self.data_acquisition_model.configure(counter_config['configure'])
        self.view.hardware_config_button.bind("<Button>", lambda e: self.data_acquisition_model.configure_view(self.root_window))
        self.animation = None  # reset the animation


def main() -> None:

    tkapp = MainTkApplication(DEFAULT_DAQ_DEVICE_NAME)
    tkapp.run()


if __name__ == '__main__':
    main()

import argparse
import collections
import tkinter as Tk
import logging
import pkg_resources
import yaml
import importlib

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import qt3utils.applications.qt3scope.interface as qt3interface

logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description='Digital input terminal rate counter.',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

# TODO -- eventually move this to adjustable option in GUI
parser.add_argument('-w', '--scope-width', metavar = 'width', default = 500, type=int,
                    help='Number of measurements to display in window.')
parser.add_argument('-r', '--randomtest', action = 'store_true',
                    help='When true, program will run showing random numbers. This is for development testing.')
# TODO -- eventually move this to adjustable option in GUI
parser.add_argument('-aut', '--animation-update-interval', metavar = 'milliseconds', default = 20,
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

DEFAULT_HARDWARE = 'NIDAQ Edge Counter'
RANDOM_DATA_GENERATOR = 'Random Data Generator'
SUPPORTED_HARDWARE = {DEFAULT_HARDWARE: 'devices/nidaq_edge_counter.yaml',
                      RANDOM_DATA_GENERATOR: 'devices/random.yaml',
                      }
CONFIG_FILE_APPLICATION_NAME = 'QT3Scope'
CONFIG_FILE_COUNTER_NAME = 'Counter'


def open_config_for_hardware(hardware_name):
    with pkg_resources.resource_stream(__name__, SUPPORTED_HARDWARE[hardware_name]) as stream:
        config = yaml.safe_load(stream)
    return config


class ScopeFigure:

    def __init__(self, width=50, fig = None, ax = None):
        if ax == None:
            fig, ax = plt.subplots(figsize=(6,4))
            self.fig = fig
            self.ax = ax
        else:
            self.fig = fig
            self.ax = ax

        self.width = width
        self.reset()

        self.line, = self.ax.plot(self.ydata)
        self.ax.set_ylabel('counts / sec')
        self.ax.ticklabel_format(style='sci',scilimits=(-3,4),axis='y')

    def init(self):
        self.line.set_ydata(self.ydata)
        return self.line,

    def reset(self, width=None):
        if width is None:
            width = self.width
        self.ydata = collections.deque(np.zeros(width))

    def update(self, y):

        self.ydata.popleft()
        self.ydata.append(y)

        #this doesn't work with blit = True.
        #there's a workaround if we need blit = true
        #https://stackoverflow.com/questions/53423868/matplotlib-animation-how-to-dynamically-extend-x-limits
        #need to sporadically call
        #fig.canvas.resize_event()

        delta = 0.1*np.max(self.ydata)
        new_min = np.max([0, np.min(self.ydata) - delta])
        new_max = np.max(self.ydata) + delta
        current_min, current_max = self.ax.get_ylim()
        if (np.abs((new_min - current_min)/(current_min)) > 0.12) or (np.abs((new_max - current_max)/(current_max)) > 0.12):
            self.ax.set_ylim(np.max([0.01, np.min(self.ydata) - delta]), np.max(self.ydata) + delta)
        self.line.set_ydata(self.ydata)
        return self.line,



class MainApplicationView():
    def __init__(self, app_controller):
        frame = Tk.Frame(app_controller.root)
        frame.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=True)

        self.scope_view = ScopeFigure(args.scope_width)
        self.sidepanel = SidePanel(app_controller)

        self.canvas = FigureCanvasTkAgg(self.scope_view.fig, master=frame)
        self.canvas.get_tk_widget().pack(side=Tk.TOP, fill=Tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(self.canvas, frame)
        toolbar.update()
        self.canvas._tkcanvas.pack(side=Tk.TOP, fill=Tk.BOTH, expand=True)

        self.canvas.draw()

    def get_start_button(self) -> Tk.Button:
        return self.sidepanel.startButton

    def get_stop_button(self) -> Tk.Button:
        return self.sidepanel.stopButton

    def get_hardware_option(self) -> str:
        return self.sidepanel.hardware_option.get()

    def set_hardware_option(self, hardware_option: str) -> None:
        self.sidepanel.hardware_option.set(hardware_option)

    def get_hardware_config_button(self) -> Tk.Button:
        return self.sidepanel.hardware_config_button

    def get_print_hardware_config_button(self) -> Tk.Button:
        return self.sidepanel.print_hardware_config

    def get_hardware_menu(self) -> Tk.OptionMenu:
        return self.sidepanel.hardware_menu

    def reset_scope(self) -> None:
        self.scope_view.reset()
        self.canvas.draw_idle()


class SidePanel():
    def __init__(self, app_controller):
        frame = Tk.Frame(app_controller.root, width=100)
        frame.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=True)

        self.startButton = Tk.Button(frame, text="Start ")
        self.startButton.pack(side="top", fill=Tk.BOTH)

        self.stopButton = Tk.Button(frame, text="Stop")
        self.stopButton.pack(side="top", fill=Tk.BOTH)

        self.hardware_option = Tk.StringVar(frame)
        self.hardware_option.set(DEFAULT_HARDWARE)  # setting the default value

        # todo - TkOptionMenu doesn't have a way, that I know of,
        # to modify the callback after instantiation. Therefore,
        # for now, we need to pass the app_controller to this class
        # so that it can be used in the callback when a hardware option is selected.
        self.hardware_menu = Tk.OptionMenu(frame,
                                           self.hardware_option,
                                           *SUPPORTED_HARDWARE.keys(),
                                           command=app_controller.hardware_option_callback)

        self.hardware_menu.pack(side="top", fill=Tk.BOTH)

        self.hardware_config_button = Tk.Button(frame, text="Configure HW")
        self.hardware_config_button.pack(side="top", fill=Tk.BOTH)

        self.print_hardware_config = Tk.Button(frame, text="Print HW Config")
        self.print_hardware_config.pack(side="top", fill=Tk.BOTH)


class MainTkApplication():

    def __init__(self, init_hardware_name):
        self.root = Tk.Tk()
        self.view = MainApplicationView(self)

        self.view.set_hardware_option(init_hardware_name)

        init_config_dict = open_config_for_hardware(init_hardware_name)
        self.load_daq_from_config_dict(init_config_dict)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.view.get_start_button().bind("<Button>", self.start_scope)
        self.view.get_stop_button().bind("<Button>", self.stop_scope)
        self.view.get_print_hardware_config_button().bind("<Button>", lambda e: self.data_acquisition_model.print_config())

        self.animation = None

    def run(self):
        logger.debug('run')
        self.root.geometry("1400x600")
        self.root.title("QT3Scope: NIDAQ Digital Input Count Rate")
        self.root.deiconify()
        self.root.mainloop()

    def stop_scope(self, event = None):
        logger.debug('clicked stop')
        self.data_acquisition_model.stop()
        if self.animation is not None:
            self.animation.pause()

        self.view.get_start_button().config(state=Tk.NORMAL)
        self.view.get_stop_button().config(state=Tk.NORMAL)
        self.view.get_hardware_menu().config(state=Tk.NORMAL)
        self.view.get_hardware_config_button().config(state=Tk.NORMAL)
        self.view.get_print_hardware_config_button().config(state=Tk.NORMAL)

    def start_scope(self, event = None):
        logger.debug('clicked start')
        if self.animation is None:
            self.view.canvas.draw_idle()
            self.animation = animation.FuncAnimation(self.view.scope_view.fig,
                                                     self.view.scope_view.update,
                                                     self.data_acquisition_model.yield_count_rate,
                                                     init_func = self.view.scope_view.init,
                                                     interval=args.animation_update_interval,
                                                     blit=False,
                                                     cache_frame_data=False)
        self.data_acquisition_model.start()
        self.animation.resume()

        self.view.get_start_button().config(state=Tk.DISABLED)
        self.view.get_stop_button().config(state=Tk.NORMAL)
        self.view.get_hardware_menu().config(state=Tk.DISABLED)
        self.view.get_hardware_config_button().config(state=Tk.DISABLED)
        self.view.get_print_hardware_config_button().config(state=Tk.DISABLED)

    def on_closing(self):
        logger.debug('closing')
        try:
            self.stop_scope()
            self.data_acquisition_model.close()
            self.root.quit()
            self.root.destroy()
        except Exception as e:
            logger.warning(e)
            pass

    def hardware_option_callback(self, *args):
        logger.info(f"New hardware option selected: {self.view.get_hardware_option()}")

        logger.debug(f"Passed args: {args}")
        # will probly need to reinstantiate the animation here.
        with pkg_resources.resource_stream(__name__, SUPPORTED_HARDWARE[self.view.get_hardware_option()]) as stream:
            config = yaml.safe_load(stream)

        self.load_daq_from_config_dict(config)
        self.view.reset_scope()

    def load_daq_from_config_dict(self, config):

        counter_config = config[CONFIG_FILE_APPLICATION_NAME][CONFIG_FILE_COUNTER_NAME]

        logger.info("loading from configuration")
        logger.info(counter_config)

        # Dynamically import the module
        module = importlib.import_module(counter_config['import_path'])

        # Dynamically instantiate the class
        cls = getattr(module, counter_config['class_name'])
        # cls should be instance of QT3ScopeDataControllerInterface
        self.data_acquisition_model = cls(logger)
        assert isinstance(self.data_acquisition_model, qt3interface.QT3ScopeDataControllerInterface)

        # configure the data acquisition model
        self.data_acquisition_model.configure(counter_config['configure'])
        self.view.get_hardware_config_button().bind("<Button>", lambda e: self.data_acquisition_model.configure_view(self.root))
        self.animation = None  # reset the animation


def main():

    hardware_name = DEFAULT_HARDWARE
    if args.randomtest:
        hardware_name = RANDOM_DATA_GENERATOR

    tkapp = MainTkApplication(hardware_name)
    tkapp.run()


if __name__ == '__main__':
    main()
